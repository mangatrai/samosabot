"""
Clan Events Cog

Point-based clan competition system. Servers define clans (as Discord roles),
create timed events, and mods award points for activities. Members and clans
accumulate scores visible via leaderboards.
"""

import io
import discord
from discord import app_commands
from discord.ext import commands, tasks
import logging
import uuid
import datetime
from utils import astra_db_ops

CURATED_ACTIVITIES = [
    "Question of the Day",
    "Picture of the Week",
    "Clue Game",
    "Bump Server",
    "Invite a Friend",
]
STATUS_EMOJI = {"draft": "📝", "active": "🟢", "ended": "🔴"}
MAX_ACTIVITIES = 8
ROLES_PER_PAGE = 20


# ==================== STATE ====================

class SetupState:
    def __init__(
        self,
        guild_id: str,
        admin_channel_id: str,
        announcement_channel_id: str,
        auto_post: bool,
        original_interaction: discord.Interaction,
    ):
        self.guild_id = guild_id
        self.admin_channel_id = admin_channel_id
        self.announcement_channel_id = announcement_channel_id
        self.auto_post = auto_post
        self.original_interaction = original_interaction
        self.clan_roles: list[discord.Role] = []
        self.mod_roles: list[discord.Role] = []


class EventCreationState:
    def __init__(self, guild_id: str, mod_id: str):
        self.guild_id = guild_id
        self.mod_id = mod_id
        self.name = ""
        self.description = ""
        self.start_date = ""
        self.end_date = ""
        self.image_url = ""  # set from attachment at command invocation time
        self.selected_curated_activities: list[str] = []
        self.activities_state: dict[str, int | None] = {}  # name → points (None = not yet set)
        self.activities: list[dict] = []
        self.form_interaction: discord.Interaction | None = None  # set after modal submit


# ==================== ROLE SELECTION (paginated multi-select) ====================
# Uses a regular Select menu with server roles as options, paginated 20 per page.
# Avoids discord.ui.RoleSelect UX issues (search clears multi-select, rendering limits).
# All interactions here are component interactions → edit_message() works throughout.

def _meaningful_roles(guild: discord.Guild) -> list[discord.Role]:
    return [
        r for r in reversed(guild.roles)
        if not r.is_bot_managed() and r.name != "@everyone" and not r.is_integration()
    ]


class PaginatedRoleSelectView(discord.ui.View):
    def __init__(
        self,
        guild: discord.Guild,
        step: str,
        state: SetupState,
        authorized_user_id: int,
        page: int = 1,
        selected_ids: set | None = None,
    ):
        super().__init__(timeout=300)
        self.guild = guild
        self.step = step
        self.state = state
        self.authorized_user_id = authorized_user_id
        self.page = page
        self.selected_ids: set[int] = selected_ids or set()
        self.all_roles = _meaningful_roles(guild)
        self.total_pages = max(1, -(-len(self.all_roles) // ROLES_PER_PAGE))  # ceiling div
        self._current_select: discord.ui.Select | None = None
        self._rebuild()

    def _page_roles(self) -> list[discord.Role]:
        start = (self.page - 1) * ROLES_PER_PAGE
        return self.all_roles[start : start + ROLES_PER_PAGE]

    def _rebuild(self):
        self.clear_items()
        page_roles = self._page_roles()

        options = [
            discord.SelectOption(
                label=r.name[:100],
                value=str(r.id),
                default=(r.id in self.selected_ids),
                emoji="✅" if r.id in self.selected_ids else None,
            )
            for r in page_roles
        ]
        if options:
            self._current_select = discord.ui.Select(
                placeholder=f"Pick roles — page {self.page}/{self.total_pages}…",
                options=options,
                min_values=0,
                max_values=len(options),
            )
            self._current_select.callback = self._on_select
            self.add_item(self._current_select)

        # Nav buttons (only if multiple pages)
        if self.total_pages > 1:
            prev_btn = discord.ui.Button(
                label="← Prev",
                style=discord.ButtonStyle.secondary,
                disabled=(self.page == 1),
            )
            prev_btn.callback = self._prev
            self.add_item(prev_btn)

            page_btn = discord.ui.Button(
                label=f"{self.page} / {self.total_pages}",
                style=discord.ButtonStyle.secondary,
                disabled=True,
            )
            self.add_item(page_btn)

            next_btn = discord.ui.Button(
                label="Next →",
                style=discord.ButtonStyle.secondary,
                disabled=(self.page == self.total_pages),
            )
            next_btn.callback = self._next
            self.add_item(next_btn)

        count = len(self.selected_ids)
        done_btn = discord.ui.Button(
            label=f"Done — {count} role{'s' if count != 1 else ''} selected" if count else "Select at least one role",
            style=discord.ButtonStyle.success if count else discord.ButtonStyle.secondary,
            emoji="✅" if count else None,
            disabled=(count == 0),
        )
        done_btn.callback = self._on_done
        self.add_item(done_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.authorized_user_id:
            await interaction.response.send_message("❌ Only the person running setup can interact here.", ephemeral=True)
            return False
        return True

    async def _on_select(self, interaction: discord.Interaction):
        page_role_ids = {r.id for r in self._page_roles()}
        selected_on_page = {int(v) for v in self._current_select.values}
        self.selected_ids -= page_role_ids
        self.selected_ids |= selected_on_page
        self._rebuild()
        embed = _build_role_select_embed(self.guild, self.step, self.selected_ids, self.state)
        await interaction.response.edit_message(embed=embed, view=self)

    async def _prev(self, interaction: discord.Interaction):
        self.page -= 1
        self._rebuild()
        embed = _build_role_select_embed(self.guild, self.step, self.selected_ids, self.state)
        await interaction.response.edit_message(embed=embed, view=self)

    async def _next(self, interaction: discord.Interaction):
        self.page += 1
        self._rebuild()
        embed = _build_role_select_embed(self.guild, self.step, self.selected_ids, self.state)
        await interaction.response.edit_message(embed=embed, view=self)

    async def _on_done(self, interaction: discord.Interaction):
        selected_roles = [r for r in self.all_roles if r.id in self.selected_ids]
        if self.step == "clan":
            self.state.clan_roles = selected_roles
            view = PaginatedRoleSelectView(self.guild, "mod", self.state, self.authorized_user_id)
            embed = _build_role_select_embed(self.guild, "mod", set(), self.state)
            await interaction.response.edit_message(
                content=(
                    "**Step 2 of 3 — Mod Roles**\n"
                    "Select the roles that can manage events and award points."
                ),
                embed=embed,
                view=view,
            )
        else:
            self.state.mod_roles = selected_roles
            embed = _build_setup_summary_embed(self.state, self.guild)
            view = SetupConfirmView(self.state, self.authorized_user_id)
            await interaction.response.edit_message(
                content="**Step 3 of 3 — Confirm Setup**\nEverything look right?",
                embed=embed,
                view=view,
            )


class SetupConfirmView(discord.ui.View):
    def __init__(self, state: SetupState, authorized_user_id: int):
        super().__init__(timeout=300)
        self.state = state
        self.authorized_user_id = authorized_user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.authorized_user_id:
            await interaction.response.send_message("❌ Only the person running setup can interact here.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Save Settings", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        settings = {
            "admin_channel_id": self.state.admin_channel_id,
            "announcement_channel_id": self.state.announcement_channel_id,
            "auto_post_announcements": self.state.auto_post,
            "clan_role_ids": [str(r.id) for r in self.state.clan_roles],
            "clan_role_names": {str(r.id): r.name for r in self.state.clan_roles},
            "mod_role_ids": [str(r.id) for r in self.state.mod_roles],
        }
        astra_db_ops.upsert_clan_event_settings(self.state.guild_id, settings)

        # Show saved settings, remove buttons
        admin_ch = guild.get_channel(int(self.state.admin_channel_id))
        announce_ch = guild.get_channel(int(self.state.announcement_channel_id))
        embed = discord.Embed(
            title="✅ Clan Events — All Set!",
            description=(
                "Your clan events system is live and ready. "
                "Use `/event create` to build your first event! 🎉"
            ),
            color=discord.Color.green(),
        )
        embed.add_field(name="Admin Channel", value=admin_ch.mention if admin_ch else "—", inline=True)
        embed.add_field(name="Announcements", value=announce_ch.mention if announce_ch else "—", inline=True)
        embed.add_field(name="Auto-Post", value="Yes ✅" if self.state.auto_post else "No ❌", inline=True)
        embed.add_field(
            name=f"Clan Roles ({len(self.state.clan_roles)})",
            value=", ".join(r.mention for r in self.state.clan_roles) or "None",
            inline=False,
        )
        embed.add_field(
            name=f"Mod Roles ({len(self.state.mod_roles)})",
            value=", ".join(r.mention for r in self.state.mod_roles) or "None",
            inline=False,
        )
        await interaction.response.edit_message(content=None, embed=embed, view=None)

    @discord.ui.button(label="← Go Back", style=discord.ButtonStyle.secondary)
    async def go_back(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = PaginatedRoleSelectView(
            interaction.guild,
            "mod",
            self.state,
            self.authorized_user_id,
            selected_ids={r.id for r in self.state.mod_roles},
        )
        embed = _build_role_select_embed(interaction.guild, "mod", {r.id for r in self.state.mod_roles}, self.state)
        await interaction.response.edit_message(
            content="**Step 2 of 3 — Mod Roles**\nSelect the roles that can manage events and award points.",
            embed=embed,
            view=view,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Setup cancelled.", embed=None, view=None)


# ==================== EVENT CREATION ====================
# Modal submissions can't edit_message directly; instead we store form_interaction
# (the modal-submit interaction) and call form_interaction.edit_original_response()
# from any subsequent modal submission.  Component interactions (buttons, selects)
# still use interaction.response.edit_message() which always works.

class EventBasicInfoModal(discord.ui.Modal):
    def __init__(self, state: EventCreationState):
        super().__init__(title="Create Event — Basic Info")
        self.state = state

        self.name_field = discord.ui.TextInput(label="Event Name", default=state.name, max_length=80, required=True)
        self.desc_field = discord.ui.TextInput(
            label="Description", style=discord.TextStyle.paragraph,
            default=state.description, max_length=500, required=False,
        )
        self.start_field = discord.ui.TextInput(
            label="Start Date  (MM/DD/YYYY)", placeholder="05/01/2026",
            default=state.start_date, required=False,
        )
        self.end_field = discord.ui.TextInput(
            label="End Date  (MM/DD/YYYY)", placeholder="05/31/2026",
            default=state.end_date, required=False,
        )
        for f in (self.name_field, self.desc_field, self.start_field, self.end_field):
            self.add_item(f)

    async def on_submit(self, interaction: discord.Interaction):
        self.state.name = self.name_field.value.strip()
        self.state.description = self.desc_field.value.strip()
        self.state.start_date = self.start_field.value.strip()
        self.state.end_date = self.end_field.value.strip()
        self.state.form_interaction = interaction  # stored for later edit_original_response()

        embed = _build_activity_select_embed(self.state.selected_curated_activities)
        view = ActivitySelectView(self.state, interaction.user.id)
        await interaction.response.send_message(
            "**Step 2 of 3 — Pick Activities**\n"
            "Choose which activities earn points in this event. "
            "Select from the list, then click **Proceed →**. "
            "You can also add custom activities on the next screen.",
            embed=embed,
            view=view,
            ephemeral=True,
        )


class ActivitySelectView(discord.ui.View):
    def __init__(self, state: EventCreationState, authorized_user_id: int):
        super().__init__(timeout=300)
        self.state = state
        self.authorized_user_id = authorized_user_id
        self._selected: list[str] = list(state.selected_curated_activities)  # preserve if coming back

        options = [
            discord.SelectOption(
                label=a,
                value=a,
                default=(a in self._selected),
                emoji="✅" if a in self._selected else None,
            )
            for a in CURATED_ACTIVITIES
        ]
        self._select = discord.ui.Select(
            placeholder="Pick activities…",
            min_values=0,
            max_values=len(options),
            options=options,
        )
        self._select.callback = self._on_select
        self.add_item(self._select)

        proceed = discord.ui.Button(label="Proceed →", style=discord.ButtonStyle.primary, emoji="▶️")
        proceed.callback = self._on_proceed
        self.add_item(proceed)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.authorized_user_id:
            await interaction.response.send_message("Only the person creating this event can interact here.", ephemeral=True)
            return False
        return True

    async def _on_select(self, interaction: discord.Interaction):
        self._selected = list(self._select.values)
        await interaction.response.defer()

    async def _on_proceed(self, interaction: discord.Interaction):
        self.state.selected_curated_activities = self._selected
        # Build activities_state: preserve existing points for re-selected activities
        new_state: dict[str, int | None] = {}
        for name in self._selected:
            new_state[name] = self.state.activities_state.get(name)
        # Also keep any custom activities that were already added
        for name, pts in self.state.activities_state.items():
            if name not in CURATED_ACTIVITIES:
                new_state[name] = pts
        self.state.activities_state = new_state

        entry_view = PointEntryView(self.state, interaction.user.id)
        embed = _build_point_entry_embed(self.state.activities_state)
        await interaction.response.edit_message(
            content=(
                "**Step 3 of 3 — Set Point Values**\n"
                "Click each activity to assign its point value. "
                "Use **+ Custom** to add your own activities.\n"
                "Hit **← Back** to change your activity selection."
            ),
            embed=embed,
            view=entry_view,
        )


# ==================== POINT ENTRY ====================
# Clicking an activity button opens a 1-field modal (no modal chaining).
# Modal submissions use state.form_interaction.edit_original_response() to
# update the ephemeral message since modal→edit_message is forbidden by Discord.

class ActivityPointButton(discord.ui.Button):
    def __init__(self, activity_name: str, pts: int | None, state: EventCreationState, idx: int):
        is_set = pts is not None
        label = (f"✅ {activity_name[:26]}  ({pts} pts)" if is_set else f"⬜ {activity_name[:28]}  — tap to set")
        super().__init__(
            label=label[:80],
            style=discord.ButtonStyle.success if is_set else discord.ButtonStyle.secondary,
            custom_id=f"actpt_{idx}",
        )
        self.activity_name = activity_name
        self.state = state

    async def callback(self, interaction: discord.Interaction):
        modal = SetSinglePointModal(self.activity_name, self.state, interaction.message)
        await interaction.response.send_modal(modal)


class AddCustomActivityButton(discord.ui.Button):
    def __init__(self, state: EventCreationState):
        disabled = len(state.activities_state) >= MAX_ACTIVITIES
        super().__init__(
            label="+ Custom" if not disabled else f"+ Custom (max {MAX_ACTIVITIES})",
            style=discord.ButtonStyle.blurple,
            emoji="✏️",
            custom_id="add_custom_act",
            disabled=disabled,
        )
        self.state = state

    async def callback(self, interaction: discord.Interaction):
        modal = AddCustomActivityModal(self.state, interaction.message)
        await interaction.response.send_modal(modal)


class BackToActivitiesButton(discord.ui.Button):
    def __init__(self, state: EventCreationState, authorized_user_id: int):
        super().__init__(label="← Back", style=discord.ButtonStyle.secondary, custom_id="back_to_activities")
        self.state = state
        self.authorized_user_id = authorized_user_id

    async def callback(self, interaction: discord.Interaction):
        embed = _build_activity_select_embed(self.state.selected_curated_activities)
        view = ActivitySelectView(self.state, self.authorized_user_id)
        await interaction.response.edit_message(
            content=(
                "**Step 2 of 3 — Pick Activities**\n"
                "Choose which activities earn points in this event. "
                "Select from the list, then click **Proceed →**. "
                "You can also add custom activities on the next screen."
            ),
            embed=embed,
            view=view,
        )


class DonePointEntryButton(discord.ui.Button):
    def __init__(self, state: EventCreationState, authorized_user_id: int):
        all_set = bool(state.activities_state) and all(v is not None for v in state.activities_state.values())
        label = "Review & Submit →" if all_set else "Set all point values first"
        super().__init__(
            label=label,
            style=discord.ButtonStyle.success if all_set else discord.ButtonStyle.secondary,
            emoji="🚀" if all_set else None,
            custom_id="done_point_entry",
            disabled=not all_set,
        )
        self.state = state
        self.authorized_user_id = authorized_user_id

    async def callback(self, interaction: discord.Interaction):
        self.state.activities = [{"name": k, "points": v} for k, v in self.state.activities_state.items()]
        embed = _build_event_summary_embed(self.state)
        view = EventSummaryView(self.state, self.authorized_user_id)
        await interaction.response.edit_message(
            content="**Review your event before submitting:**",
            embed=embed,
            view=view,
        )


class PointEntryView(discord.ui.View):
    def __init__(self, state: EventCreationState, authorized_user_id: int):
        super().__init__(timeout=300)
        self.state = state
        self.authorized_user_id = authorized_user_id
        self._rebuild()

    def _rebuild(self):
        self.clear_items()
        for i, (name, pts) in enumerate(self.state.activities_state.items()):
            self.add_item(ActivityPointButton(name, pts, self.state, i))
        self.add_item(AddCustomActivityButton(self.state))
        self.add_item(BackToActivitiesButton(self.state, self.authorized_user_id))
        self.add_item(DonePointEntryButton(self.state, self.authorized_user_id))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.authorized_user_id:
            await interaction.response.send_message("Only the person creating this event can interact here.", ephemeral=True)
            return False
        return True

    async def refresh(self):
        """Rebuild and push to the ephemeral message via form_interaction."""
        self._rebuild()
        embed = _build_point_entry_embed(self.state.activities_state)
        try:
            await self.state.form_interaction.edit_original_response(
                content=(
                    "**Step 3 of 3 — Set Point Values**\n"
                    "Click each activity to assign its point value. "
                    "Use **+ Custom** to add your own activities.\n"
                    "Hit **← Back** to change your activity selection."
                ),
                embed=embed,
                view=self,
            )
        except Exception as e:
            logging.error(f"PointEntryView.refresh failed: {e}")


class SetSinglePointModal(discord.ui.Modal):
    def __init__(self, activity_name: str, state: EventCreationState, _message: discord.Message):
        super().__init__(title=f"Points: {activity_name[:40]}")
        self.activity_name = activity_name
        self.state = state

        existing = state.activities_state.get(activity_name)
        self.pts_input = discord.ui.TextInput(
            label=f"Points for {activity_name[:40]}",
            placeholder="e.g. 10",
            default=str(existing) if existing is not None else "",
            max_length=6,
            required=True,
        )
        self.add_item(self.pts_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            pts = int(self.pts_input.value.strip())
            if pts <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Points must be a positive whole number.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        self.state.activities_state[self.activity_name] = pts
        entry_view = PointEntryView(self.state, interaction.user.id)
        await entry_view.refresh()


class AddCustomActivityModal(discord.ui.Modal, title="Add Custom Activity"):
    def __init__(self, state: EventCreationState, _message: discord.Message):
        super().__init__(title="Add Custom Activity")
        self.state = state

        self.name_input = discord.ui.TextInput(
            label="Activity Name",
            placeholder="e.g. Weekly Riddle Winner",
            max_length=60,
            required=True,
        )
        self.pts_input = discord.ui.TextInput(
            label="Points for this activity",
            placeholder="e.g. 50",
            max_length=6,
            required=True,
        )
        self.add_item(self.name_input)
        self.add_item(self.pts_input)

    async def on_submit(self, interaction: discord.Interaction):
        name = self.name_input.value.strip()
        try:
            pts = int(self.pts_input.value.strip())
            if pts <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Points must be a positive whole number.", ephemeral=True)
            return
        if name in self.state.activities_state:
            await interaction.response.send_message(f"❌ **{name}** is already in the activity list.", ephemeral=True)
            return
        if len(self.state.activities_state) >= MAX_ACTIVITIES:
            await interaction.response.send_message(f"❌ Maximum {MAX_ACTIVITIES} activities per event.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        self.state.activities_state[name] = pts
        entry_view = PointEntryView(self.state, interaction.user.id)
        await entry_view.refresh()


# ==================== EVENT SUMMARY ====================

class EventSummaryView(discord.ui.View):
    def __init__(self, state: EventCreationState, authorized_user_id: int):
        super().__init__(timeout=300)
        self.state = state
        self.authorized_user_id = authorized_user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.authorized_user_id:
            await interaction.response.send_message("Only the person creating this event can interact here.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Submit Event 🚀", style=discord.ButtonStyle.success)
    async def submit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        event_id = f"evt_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        event_data = {
            "event_id": event_id,
            "name": self.state.name,
            "description": self.state.description,
            "start_date": self.state.start_date,
            "end_date": self.state.end_date,
            "image_url": self.state.image_url,
            "activities": self.state.activities,
            "status": "draft",
            "created_by": self.state.mod_id,
        }
        result = astra_db_ops.create_clan_event(self.state.guild_id, event_data)
        if result is None:
            await interaction.followup.send("❌ Failed to save event to database. Please try again.", ephemeral=True)
            return

        # Final state: show saved event summary, no buttons
        embed = _build_event_summary_embed(self.state)
        embed.title = f"✅ Event Saved — {self.state.name}"
        embed.color = discord.Color.green()
        hint = "" if self.state.image_url else "\n💡 No banner image — use `/event setbanner` to add one anytime."
        embed.description = (
            f"{embed.description or ''}\n\n"
            f"**Status:** Draft — use `/event start` when you're ready to go live! 🚀{hint}"
        )
        await self.state.form_interaction.edit_original_response(
            content=None, embed=embed, view=None
        )

    @discord.ui.button(label="← Edit Info", style=discord.ButtonStyle.secondary, emoji="✏️")
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EventBasicInfoModal(self.state))

    @discord.ui.button(label="← Change Activities", style=discord.ButtonStyle.secondary)
    async def change_activities(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = _build_activity_select_embed(self.state.selected_curated_activities)
        view = ActivitySelectView(self.state, self.authorized_user_id)
        await interaction.response.edit_message(
            content=(
                "**Step 2 of 3 — Pick Activities**\n"
                "Choose which activities earn points in this event."
            ),
            embed=embed,
            view=view,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="✖️")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Event creation cancelled.", embed=None, view=None)


# ==================== EMBED BUILDERS ====================

def _build_role_select_embed(
    guild: discord.Guild,
    step: str,
    selected_ids: set[int],
    state: SetupState,
) -> discord.Embed:
    step_name = "Clan" if step == "clan" else "Mod"
    step_num = "1" if step == "clan" else "2"
    desc = (
        "Select the Discord roles that represent **clans**. "
        "Members are matched to their clan based on their first matching role."
        if step == "clan"
        else "Select the roles that can **create/start events** and **award points** to members."
    )
    embed = discord.Embed(
        title=f"Step {step_num} of 3 — {step_name} Roles",
        description=desc,
        color=discord.Color.blue(),
    )
    if step == "mod" and state.clan_roles:
        embed.add_field(
            name="✅ Clan Roles (saved)",
            value=", ".join(r.mention for r in state.clan_roles) or "None",
            inline=False,
        )
    if selected_ids:
        names = [r.name for r in _meaningful_roles(guild) if r.id in selected_ids]
        embed.add_field(name=f"Currently Selected ({len(selected_ids)})", value=", ".join(names), inline=False)
    embed.set_footer(text="Use the dropdown above • selections carry across pages")
    return embed


def _build_setup_summary_embed(state: SetupState, guild: discord.Guild) -> discord.Embed:
    admin_ch = guild.get_channel(int(state.admin_channel_id))
    announce_ch = guild.get_channel(int(state.announcement_channel_id))
    embed = discord.Embed(title="⚙️ Setup Summary", color=discord.Color.gold())
    embed.add_field(name="Admin Channel", value=admin_ch.mention if admin_ch else "—", inline=True)
    embed.add_field(name="Announcement Channel", value=announce_ch.mention if announce_ch else "—", inline=True)
    embed.add_field(name="Auto-Post", value="Yes ✅" if state.auto_post else "No ❌", inline=True)
    embed.add_field(
        name=f"Clan Roles ({len(state.clan_roles)})",
        value=", ".join(r.mention for r in state.clan_roles) or "None",
        inline=False,
    )
    embed.add_field(
        name=f"Mod Roles ({len(state.mod_roles)})",
        value=", ".join(r.mention for r in state.mod_roles) or "None",
        inline=False,
    )
    return embed


def _build_activity_select_embed(pre_selected: list[str]) -> discord.Embed:
    embed = discord.Embed(
        title="🎯 Select Event Activities",
        description=(
            "Pick which of the curated activities below will earn points in this event.\n"
            "You can **add custom activities** on the next screen.\n\n"
            "If you want only custom activities, click **Proceed →** without selecting anything."
        ),
        color=discord.Color.blurple(),
    )
    lines = [f"• {a}" for a in CURATED_ACTIVITIES]
    embed.add_field(name="Curated Activities", value="\n".join(lines), inline=False)
    return embed


def _build_point_entry_embed(activities_state: dict[str, int | None]) -> discord.Embed:
    embed = discord.Embed(title="🏆 Activity Point Values", color=discord.Color.gold())
    if not activities_state:
        embed.description = "No activities yet — use **+ Custom** to add your own, or go **← Back** to pick curated ones."
        return embed
    lines = []
    all_set = True
    for name, pts in activities_state.items():
        if pts is not None:
            lines.append(f"✅ **{name}** — {pts} pts")
        else:
            lines.append(f"⬜ **{name}** — *tap button to set*")
            all_set = False
    embed.description = "\n".join(lines)
    embed.set_footer(text="All points set! Hit Review & Submit → to continue." if all_set else "Click an activity button to set its point value.")
    return embed


def _build_event_summary_embed(state: EventCreationState) -> discord.Embed:
    embed = discord.Embed(title=f"📋 {state.name}", color=discord.Color.blurple())
    if state.description:
        embed.description = state.description
    if state.start_date or state.end_date:
        embed.add_field(name="📅 Dates", value=f"{state.start_date or '?'} → {state.end_date or '?'}", inline=True)
    acts = "\n".join(f"• **{a['name']}** — {a['points']} pts" for a in state.activities)
    embed.add_field(name="🎯 Activities", value=acts or "None set", inline=False)
    if state.image_url:
        embed.set_image(url=state.image_url)
    return embed


def _build_event_announcement_embed(event: dict, action: str) -> discord.Embed:
    name = event.get("name", "Event")
    acts = event.get("activities", [])
    image_url = event.get("image_url", "")

    if action == "start":
        embed = discord.Embed(
            title=f"🔥 {name} is LIVE!",
            description=(
                f"**The wait is over — {name} has officially begun!** 🎉\n\n"
                "Whether you're a competitive powerhouse or just here to rep your clan — "
                "every single point counts and every move gets your clan closer to glory. "
                "Your clan needs YOU. Don't sit this one out! 🦁"
            ),
            color=discord.Color.from_rgb(255, 100, 0),
        )
        if event.get("description"):
            embed.add_field(name="What's it about?", value=event["description"], inline=False)
        if acts:
            embed.add_field(
                name="🎯 Earn Points By…",
                value="\n".join(f"• **{a['name']}** — {a['points']} pts" for a in acts),
                inline=False,
            )
        if event.get("start_date") or event.get("end_date"):
            embed.add_field(name="📅 Event Window", value=f"{event.get('start_date','?')} → {event.get('end_date','?')}", inline=False)
        embed.set_footer(text="Show up. Earn. Win. Your clan is counting on you. 💪")

    elif action == "stop":
        embed = discord.Embed(
            title=f"🏁 {name} — That's a Wrap!",
            description=(
                f"**{name} has officially closed!** 🎊\n\n"
                "What a run it's been! The dust is settling, the scores are tallied, "
                "and the final standings are **LOCKED**. 🔒\n\n"
                "Check out the results below — some clans brought fire 🔥, "
                "others have some leveling up to do 😄\n\n"
                "*Big respect to every participant who showed up and competed. See you at the next one!* ✌️"
            ),
            color=discord.Color.from_rgb(80, 80, 80),
        )
    else:
        embed = discord.Embed(
            title=f"📣 New Event Incoming: {name}",
            description=(
                f"Heads up — **{name}** is coming your way! 👀\n\n"
                f"{event.get('description', 'A new event has been created.')}"
            ),
            color=discord.Color.blue(),
        )
        if acts:
            embed.add_field(
                name="🎯 Activities & Points",
                value="\n".join(f"• **{a['name']}** — {a['points']} pts" for a in acts),
                inline=False,
            )
        embed.set_footer(text="Stay tuned — event starts soon! Get ready! 🚀")

    if image_url:
        embed.set_image(url=image_url)
    return embed


def _progress_bar(value: int, max_value: int, width: int = 12) -> str:
    if max_value == 0:
        return "░" * width
    filled = round((value / max_value) * width)
    return "█" * filled + "░" * (width - filled)


def _build_leaderboard_embed(
    target_member: discord.Member,
    member_scores: list,
    clan_scores: list,
    event: dict = None,
    alltime_member_scores: list = None,
    alltime_clan_scores: list = None,
) -> discord.Embed:
    is_event_view = event is not None
    title = f"📊  {event['name'].upper()}" if is_event_view else "📊  ALL-TIME STANDINGS"
    color = discord.Color.gold() if is_event_view else discord.Color.from_rgb(100, 80, 200)

    embed = discord.Embed(title=title, color=color)

    if is_event_view:
        status = STATUS_EMOJI.get(event.get("status", ""), "")
        embed.description = (
            f"{status} **Status:** {event.get('status', '?').title()}"
            + (f"  •  📅 {event.get('start_date','?')} → {event.get('end_date','?')}" if event.get("start_date") else "")
        )

    uid = str(target_member.id)

    def rank_and_pts(scores, uid):
        for i, s in enumerate(scores, 1):
            if s["user_id"] == uid:
                return i, s["total_points"]
        return None, 0

    def clan_stat(clan_list, clan_id):
        for i, c in enumerate(clan_list, 1):
            if c["clan_role_id"] == clan_id:
                return i, c["total_points"], c.get("avg_points", 0)
        return None, 0, 0

    user_entry = next((s for s in (member_scores or []) if s["user_id"] == uid), None)
    if not user_entry and alltime_member_scores:
        user_entry = next((s for s in alltime_member_scores if s["user_id"] == uid), None)
    clan_role_id = user_entry.get("clan_role_id") if user_entry else None
    clan_name = user_entry.get("clan_name", "No Clan") if user_entry else "No Clan"

    medals = ["🥇", "🥈", "🥉"]

    # — User stats —
    user_lines = []
    if is_event_view and member_scores is not None:
        rank, pts = rank_and_pts(member_scores, uid)
        rank_str = f"  {medals[rank-1] if rank and rank <= 3 else f'#{rank}'}" if rank else "  (unranked)"
        user_lines.append(f"**Event Score:** `{pts:,} pts`{rank_str}")
    if alltime_member_scores is not None:
        rank, pts = rank_and_pts(alltime_member_scores, uid)
        rank_str = f"  {medals[rank-1] if rank and rank <= 3 else f'#{rank}'}" if rank else "  (unranked)"
        user_lines.append(f"**All-Time:** `{pts:,} pts`{rank_str}")
    elif member_scores is not None and not is_event_view:
        rank, pts = rank_and_pts(member_scores, uid)
        rank_str = f"  {medals[rank-1] if rank and rank <= 3 else f'#{rank}'}" if rank else "  (unranked)"
        user_lines.append(f"**All-Time:** `{pts:,} pts`{rank_str}")

    embed.add_field(
        name=f"👤  {target_member.display_name}",
        value="\n".join(user_lines) if user_lines else "No score yet — get out there! 🏃",
        inline=False,
    )

    # — Clan stats —
    clan_lines = []
    if clan_role_id:
        if is_event_view and clan_scores is not None:
            rank, total, avg = clan_stat(clan_scores, clan_role_id)
            max_total = clan_scores[0]["total_points"] if clan_scores else 1
            bar = _progress_bar(total, max_total)
            rank_str = f"  {medals[rank-1] if rank and rank <= 3 else f'#{rank}'}" if rank else ""
            clan_lines.append(f"**Event:** `{total:,} pts`  avg `{avg}`{rank_str}\n`{bar}`")
        if alltime_clan_scores is not None:
            rank, total, avg = clan_stat(alltime_clan_scores, clan_role_id)
            max_total = alltime_clan_scores[0]["total_points"] if alltime_clan_scores else 1
            bar = _progress_bar(total, max_total)
            rank_str = f"  {medals[rank-1] if rank and rank <= 3 else f'#{rank}'}" if rank else ""
            clan_lines.append(f"**All-Time:** `{total:,} pts`  avg `{avg}`{rank_str}\n`{bar}`")
        elif clan_scores is not None and not is_event_view:
            rank, total, avg = clan_stat(clan_scores, clan_role_id)
            max_total = clan_scores[0]["total_points"] if clan_scores else 1
            bar = _progress_bar(total, max_total)
            rank_str = f"  {medals[rank-1] if rank and rank <= 3 else f'#{rank}'}" if rank else ""
            clan_lines.append(f"**All-Time:** `{total:,} pts`  avg `{avg}`{rank_str}\n`{bar}`")

    embed.add_field(
        name=f"🏰  Clan: {clan_name}",
        value="\n".join(clan_lines) if clan_lines else "No clan data yet",
        inline=False,
    )

    # — Top 5 members —
    top_members = member_scores if is_event_view else (alltime_member_scores or member_scores or [])
    if top_members:
        lines = []
        for i, s in enumerate(top_members[:5], 1):
            medal = medals[i - 1] if i <= 3 else f"`{i}.`"
            you = " ← **you**" if s["user_id"] == uid else ""
            clan_tag = f"  *({s['clan_name']})*" if s.get("clan_name") else ""
            lines.append(f"{medal}  **{s['username']}** — `{s['total_points']:,} pts`{clan_tag}{you}")
        label = f"🏅  Top Members — {'Event' if is_event_view else 'All-Time'}"
        embed.add_field(name=label, value="\n".join(lines), inline=False)

    # — Clan rankings —
    top_clans = clan_scores if is_event_view else (alltime_clan_scores or clan_scores or [])
    if top_clans:
        max_total = top_clans[0]["total_points"] if top_clans else 1
        lines = []
        for i, c in enumerate(top_clans[:5], 1):
            medal = medals[i - 1] if i <= 3 else f"`{i}.`"
            bar = _progress_bar(c["total_points"], max_total, 8)
            you_clan = " ← **yours**" if c["clan_role_id"] == clan_role_id else ""
            lines.append(
                f"{medal}  **{c['clan_name']}**  `{c['total_points']:,} pts`  avg `{c.get('avg_points',0)}`{you_clan}\n"
                f"   `{bar}`"
            )
        label = f"🏆  Clan Rankings — {'Event' if is_event_view else 'All-Time'}"
        embed.add_field(name=label, value="\n".join(lines), inline=False)

    embed.set_footer(text=f"Requested by {target_member.display_name}  •  Points = base awards + adjustments")
    return embed


def _build_daily_recap_embed(active_events: list, clan_scores_by_event: dict) -> discord.Embed:
    embed = discord.Embed(
        title="⚡  DAILY CLAN UPDATE",
        description=(
            "The competition is **LIVE** and clans are fighting for supremacy! 🔥\n"
            "Here's where things stand — is your clan on top, or is it time to grind? 👀\n\n"
            "Every activity you complete lifts your clan up the board. **Get in there!** 💪"
        ),
        color=discord.Color.from_rgb(255, 140, 0),
    )
    medals = ["🥇", "🥈", "🥉"]
    for event in active_events:
        eid = event["event_id"]
        clan_rankings = clan_scores_by_event.get(eid, [])
        if clan_rankings:
            max_pts = clan_rankings[0]["total_points"] or 1
            lines = []
            for i, c in enumerate(clan_rankings[:3], 1):
                bar = _progress_bar(c["total_points"], max_pts, 8)
                lines.append(
                    f"{medals[i-1]}  **{c['clan_name']}** `{c['total_points']:,} pts`  avg `{c.get('avg_points',0)}`\n"
                    f"   `{bar}`"
                )
            value = "\n".join(lines)
        else:
            value = "No scores yet — first mover advantage is YOURS! 🚀"
        end_tag = f"  •  Ends {event['end_date']}" if event.get("end_date") else ""
        embed.add_field(name=f"🟢  {event['name']}{end_tag}", value=value, inline=False)
    embed.set_footer(text="Participate. Earn. Dominate. Your clan is counting on you! 👑")
    return embed


def _build_settings_embed(settings: dict, guild: discord.Guild) -> discord.Embed:
    embed = discord.Embed(title="⚙️  Clan Events — Current Settings", color=discord.Color.blue())

    admin_ch_id = settings.get("admin_channel_id")
    announce_ch_id = settings.get("announcement_channel_id")
    admin_ch = guild.get_channel(int(admin_ch_id)) if admin_ch_id else None
    announce_ch = guild.get_channel(int(announce_ch_id)) if announce_ch_id else None

    embed.add_field(name="Admin Channel", value=admin_ch.mention if admin_ch else "Not set", inline=True)
    embed.add_field(name="Announcement Channel", value=announce_ch.mention if announce_ch else "Not set", inline=True)
    embed.add_field(name="Auto-Post", value="Yes ✅" if settings.get("auto_post_announcements") else "No ❌", inline=True)

    clan_role_ids = settings.get("clan_role_ids", [])
    roles_text = "  ".join(f"<@&{rid}>" for rid in clan_role_ids) if clan_role_ids else "None configured"
    embed.add_field(name=f"Clan Roles ({len(clan_role_ids)})", value=roles_text, inline=False)

    mod_role_ids = settings.get("mod_role_ids", [])
    mod_text = "  ".join(f"<@&{rid}>" for rid in mod_role_ids) if mod_role_ids else "None configured"
    embed.add_field(name=f"Mod Roles ({len(mod_role_ids)})", value=mod_text, inline=False)

    embed.set_footer(text="Run /events setup to change these settings")
    return embed


# ==================== HELPERS ====================

def _disable_view(view: discord.ui.View):
    for item in view.children:
        item.disabled = True


# ==================== COG ====================

class ClanEvents(commands.Cog):
    events_group = app_commands.Group(name="events", description="Clan events system setup")
    event_group = app_commands.Group(name="event", description="Event and scoring commands")

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def cog_unload(self):
        self.daily_recap.cancel()

    # ---- Permission helpers ----

    async def _check_mod(self, interaction: discord.Interaction) -> bool:
        member = interaction.user
        if member.guild_permissions.manage_guild:
            return True
        settings = astra_db_ops.get_clan_event_settings(str(interaction.guild_id))
        if settings:
            mod_ids = set(settings.get("mod_role_ids", []))
            if {str(r.id) for r in member.roles} & mod_ids:
                return True
        return False

    def _get_user_clan(self, member: discord.Member, clan_role_ids: list[str]) -> tuple[str | None, str | None]:
        member_role_ids = {str(r.id) for r in member.roles}
        for role_id in clan_role_ids:
            if role_id in member_role_ids:
                role = member.guild.get_role(int(role_id))
                if role:
                    return role_id, role.name
        return None, None

    # ---- Autocomplete ----

    async def _active_event_ac(self, interaction: discord.Interaction, current: str):
        events = astra_db_ops.get_clan_events(str(interaction.guild_id), status="active")
        return [
            app_commands.Choice(name=e["name"], value=e["name"])
            for e in events if current.lower() in e["name"].lower()
        ][:25]

    async def _any_event_ac(self, interaction: discord.Interaction, current: str):
        events = astra_db_ops.get_clan_events(str(interaction.guild_id))
        return [
            app_commands.Choice(name=f"{STATUS_EMOJI.get(e.get('status',''), '')} {e['name']}", value=e["name"])
            for e in events if current.lower() in e["name"].lower()
        ][:25]

    async def _activity_ac(self, interaction: discord.Interaction, current: str):
        event_name = interaction.namespace.event_name
        if not event_name:
            return []
        event = astra_db_ops.get_clan_event_by_name(str(interaction.guild_id), event_name)
        if not event:
            return []
        return [
            app_commands.Choice(name=a["name"], value=a["name"])
            for a in event.get("activities", []) if current.lower() in a["name"].lower()
        ][:25]

    # ---- Background task ----

    @tasks.loop(hours=24)
    async def daily_recap(self):
        try:
            col = astra_db_ops.get_clan_event_settings_collection()
            guilds = list(col.find({"auto_post_announcements": True})) if col else []
        except Exception as e:
            logging.error(f"Daily recap: error fetching settings: {e}")
            return

        for settings in guilds:
            guild_id = settings.get("guild_id")
            channel_id = settings.get("announcement_channel_id")
            if not guild_id or not channel_id:
                continue
            try:
                active_events = astra_db_ops.get_clan_events(guild_id, status="active")
                if not active_events:
                    continue
                clan_scores_by_event = {}
                for event in active_events:
                    ms = astra_db_ops.get_clan_event_leaderboard(guild_id, event["event_id"])
                    clan_scores_by_event[event["event_id"]] = astra_db_ops.get_clan_rankings(ms)
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    await channel.send(embed=_build_daily_recap_embed(active_events, clan_scores_by_event))
            except Exception as e:
                logging.error(f"Daily recap: error for guild {guild_id}: {e}")

    @daily_recap.before_loop
    async def before_daily_recap(self):
        await self.bot.wait_until_ready()

    # ---- /events setup ----

    @events_group.command(name="setup", description="Configure the clan events system (Manage Server required)")
    @app_commands.describe(
        admin_channel="Channel for admin notifications",
        announcement_channel="Channel for public event announcements and daily recaps",
        auto_post="Auto-post event start/stop announcements and daily recaps",
    )
    @app_commands.guild_only()
    async def events_setup(
        self,
        interaction: discord.Interaction,
        admin_channel: discord.TextChannel,
        announcement_channel: discord.TextChannel,
        auto_post: bool = True,
    ):
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You need **Manage Server** permission to run setup.", ephemeral=True)
            return

        state = SetupState(
            guild_id=str(interaction.guild_id),
            admin_channel_id=str(admin_channel.id),
            announcement_channel_id=str(announcement_channel.id),
            auto_post=auto_post,
            original_interaction=interaction,
        )
        embed = _build_role_select_embed(interaction.guild, "clan", set(), state)
        view = PaginatedRoleSelectView(interaction.guild, "clan", state, interaction.user.id)
        await interaction.response.send_message(
            "**Step 1 of 3 — Clan Roles**\n"
            "Select the Discord roles that represent clans in your server.",
            embed=embed,
            view=view,
            ephemeral=True,
        )

    # ---- /events settings ----

    @events_group.command(name="settings", description="View current clan events configuration for this server")
    @app_commands.guild_only()
    async def events_settings(self, interaction: discord.Interaction):
        if not await self._check_mod(interaction):
            await interaction.response.send_message("❌ You don't have permission to view settings.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        settings = astra_db_ops.get_clan_event_settings(str(interaction.guild_id))
        if not settings:
            await interaction.followup.send(
                "No configuration found. Run `/events setup` to get started.", ephemeral=True
            )
            return
        embed = _build_settings_embed(settings, interaction.guild)
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ---- /event create ----

    _ALLOWED_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")

    @event_group.command(name="create", description="Create a new event (mod only)")
    @app_commands.describe(image="Optional banner image to attach now (png, jpg, jpeg, webp)")
    @app_commands.guild_only()
    async def event_create(self, interaction: discord.Interaction, image: discord.Attachment = None):
        if not await self._check_mod(interaction):
            await interaction.response.send_message("❌ You don't have permission to create events.", ephemeral=True)
            return
        if not astra_db_ops.get_clan_event_settings(str(interaction.guild_id)):
            await interaction.response.send_message(
                "❌ Clan events not configured yet. Ask an admin to run `/events setup` first.", ephemeral=True
            )
            return
        if image and not any(image.filename.lower().endswith(ext) for ext in self._ALLOWED_IMAGE_EXTS):
            await interaction.response.send_message(
                f"❌ **{image.filename}** is not a supported image type. Use PNG, JPG, JPEG, or WEBP.",
                ephemeral=True,
            )
            return
        state = EventCreationState(guild_id=str(interaction.guild_id), mod_id=str(interaction.user.id))
        if image:
            state.image_url = image.url
        await interaction.response.send_modal(EventBasicInfoModal(state))

    # ---- /event start ----

    @event_group.command(name="start", description="Start a draft event (mod only)")
    @app_commands.describe(event_name="Name of the event to start")
    @app_commands.guild_only()
    async def event_start(self, interaction: discord.Interaction, event_name: str):
        if not await self._check_mod(interaction):
            await interaction.response.send_message("❌ You don't have permission to start events.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)
        event = astra_db_ops.get_clan_event_by_name(guild_id, event_name)
        if not event:
            await interaction.followup.send(f"❌ No event named **{event_name}** found.", ephemeral=True)
            return
        if event["status"] == "active":
            await interaction.followup.send(f"⚠️ **{event_name}** is already active.", ephemeral=True)
            return
        if event["status"] == "ended":
            await interaction.followup.send(f"❌ **{event_name}** has already ended.", ephemeral=True)
            return

        astra_db_ops.update_clan_event_status(guild_id, event["event_id"], "active")
        await interaction.followup.send(f"✅ **{event_name}** is now LIVE! 🔥", ephemeral=True)

        settings = astra_db_ops.get_clan_event_settings(guild_id)
        if settings and settings.get("auto_post_announcements") and settings.get("announcement_channel_id"):
            channel = interaction.guild.get_channel(int(settings["announcement_channel_id"]))
            if channel:
                await channel.send(embed=_build_event_announcement_embed(event, "start"))

    @event_start.autocomplete("event_name")
    async def _start_ac(self, interaction, current):
        events = astra_db_ops.get_clan_events(str(interaction.guild_id))
        return [
            app_commands.Choice(name=e["name"], value=e["name"])
            for e in events if e.get("status") == "draft" and current.lower() in e["name"].lower()
        ][:25]

    # ---- /event stop ----

    @event_group.command(name="stop", description="Stop an active event (mod only)")
    @app_commands.describe(event_name="Name of the event to stop")
    @app_commands.guild_only()
    async def event_stop(self, interaction: discord.Interaction, event_name: str):
        if not await self._check_mod(interaction):
            await interaction.response.send_message("❌ You don't have permission to stop events.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)
        event = astra_db_ops.get_clan_event_by_name(guild_id, event_name)
        if not event:
            await interaction.followup.send(f"❌ No event named **{event_name}** found.", ephemeral=True)
            return
        if event["status"] != "active":
            await interaction.followup.send(f"⚠️ **{event_name}** is not currently active.", ephemeral=True)
            return

        astra_db_ops.update_clan_event_status(guild_id, event["event_id"], "ended")
        await interaction.followup.send(f"✅ **{event_name}** has been stopped.", ephemeral=True)

        settings = astra_db_ops.get_clan_event_settings(guild_id)
        if settings and settings.get("auto_post_announcements") and settings.get("announcement_channel_id"):
            channel = interaction.guild.get_channel(int(settings["announcement_channel_id"]))
            if channel:
                await channel.send(embed=_build_event_announcement_embed(event, "stop"))
                ms = astra_db_ops.get_clan_event_leaderboard(guild_id, event["event_id"])
                clan_rankings = astra_db_ops.get_clan_rankings(ms)
                if ms or clan_rankings:
                    lb = _build_leaderboard_embed(interaction.user, ms, clan_rankings, event=event)
                    lb.title = f"🏆  FINAL STANDINGS — {event['name'].upper()}"
                    await channel.send(embed=lb)

    @event_stop.autocomplete("event_name")
    async def _stop_ac(self, interaction, current):
        return await self._active_event_ac(interaction, current)

    # ---- /event list ----

    @event_group.command(name="list", description="List all events and their activities for this server")
    @app_commands.guild_only()
    async def event_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        events = astra_db_ops.get_clan_events(str(interaction.guild_id))
        if not events:
            await interaction.followup.send(
                "No events found. Ask a mod to create one with `/event create`.", ephemeral=True
            )
            return
        embed = discord.Embed(title="📋  Events", color=discord.Color.blurple())
        for e in events[:20]:
            icon = STATUS_EMOJI.get(e.get("status", "draft"), "📝")
            dates = f"  •  {e['start_date']} → {e.get('end_date', '?')}" if e.get("start_date") else ""
            activities = e.get("activities", [])
            acts_lines = "\n".join(f"  `{a['points']} pts`  {a['name']}" for a in activities)
            value = f"**{e.get('status', 'draft').title()}**{dates}"
            if acts_lines:
                value += f"\n{acts_lines}"
            embed.add_field(name=f"{icon}  {e['name']}", value=value, inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ---- /event award ----

    @event_group.command(name="award", description="Award activity points to a member (mod only)")
    @app_commands.describe(member="Member to award", event_name="Event name", activity="Activity completed")
    @app_commands.guild_only()
    async def event_award(self, interaction: discord.Interaction, member: discord.Member, event_name: str, activity: str):
        if not await self._check_mod(interaction):
            await interaction.response.send_message("❌ You don't have permission to award points.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        settings = astra_db_ops.get_clan_event_settings(guild_id)
        if not settings:
            await interaction.followup.send("❌ Clan events not configured. Run `/events setup` first.", ephemeral=True)
            return
        event = astra_db_ops.get_clan_event_by_name(guild_id, event_name)
        if not event:
            await interaction.followup.send(f"❌ Event **{event_name}** not found.", ephemeral=True)
            return
        activity_map = {a["name"]: a["points"] for a in event.get("activities", [])}
        if activity not in activity_map:
            await interaction.followup.send(
                f"❌ **{activity}** not found in this event. Available: {', '.join(activity_map) or 'none'}", ephemeral=True
            )
            return

        clan_role_id, clan_name = self._get_user_clan(member, settings.get("clan_role_ids", []))
        points = activity_map[activity]
        astra_db_ops.award_clan_points(
            guild_id=guild_id, event_id=event["event_id"],
            user_id=str(member.id), username=member.display_name,
            activity_name=activity, clan_role_id=clan_role_id or "",
            clan_name=clan_name or "No Clan", points=points,
        )
        clan_tag = f"  (Clan: **{clan_name}**)" if clan_name else "  *(no clan role assigned)*"
        await interaction.followup.send(
            f"✅  **+{points} pts** → {member.mention}  for **{activity}**  in **{event_name}**{clan_tag}",
            ephemeral=True,
        )

    @event_award.autocomplete("event_name")
    async def _award_event_ac(self, interaction, current):
        return await self._active_event_ac(interaction, current)

    @event_award.autocomplete("activity")
    async def _award_activity_ac(self, interaction, current):
        return await self._activity_ac(interaction, current)

    # ---- /event adjust ----

    @event_group.command(name="adjust", description="Manually adjust a member's points with audit trail (mod only)")
    @app_commands.describe(
        member="Member to adjust",
        event_name="Event name",
        points="Points to add (positive) or subtract (negative)",
        reason="Required — stored in the audit log",
    )
    @app_commands.guild_only()
    async def event_adjust(
        self, interaction: discord.Interaction, member: discord.Member,
        event_name: str, points: int, reason: str,
    ):
        if not await self._check_mod(interaction):
            await interaction.response.send_message("❌ You don't have permission to adjust points.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        settings = astra_db_ops.get_clan_event_settings(guild_id)
        if not settings:
            await interaction.followup.send("❌ Clan events not configured. Run `/events setup` first.", ephemeral=True)
            return
        event = astra_db_ops.get_clan_event_by_name(guild_id, event_name)
        if not event:
            await interaction.followup.send(f"❌ Event **{event_name}** not found.", ephemeral=True)
            return

        clan_role_id, clan_name = self._get_user_clan(member, settings.get("clan_role_ids", []))
        astra_db_ops.record_clan_adjustment(
            guild_id=guild_id, event_id=event["event_id"],
            user_id=str(member.id), username=member.display_name,
            clan_role_id=clan_role_id or "", clan_name=clan_name or "No Clan",
            points=points, reason=reason,
            mod_user_id=str(interaction.user.id), mod_username=interaction.user.display_name,
        )
        sign = "+" if points >= 0 else ""
        await interaction.followup.send(
            f"📋  Adjustment logged:  **{sign}{points} pts**  for {member.mention}  in **{event_name}**\n"
            f"Reason: *{reason}*",
            ephemeral=True,
        )

    @event_adjust.autocomplete("event_name")
    async def _adjust_event_ac(self, interaction, current):
        return await self._any_event_ac(interaction, current)

    # ---- /event setbanner ----

    @event_group.command(name="setbanner", description="Add or replace the banner image for an existing event (mod only)")
    @app_commands.describe(
        event_name="Event to update",
        image="Image file to upload (png, jpg, jpeg, webp)",
    )
    @app_commands.guild_only()
    async def event_setbanner(
        self, interaction: discord.Interaction,
        event_name: str, image: discord.Attachment,
    ):
        if not await self._check_mod(interaction):
            await interaction.response.send_message("❌ You don't have permission to update events.", ephemeral=True)
            return

        if not any(image.filename.lower().endswith(ext) for ext in self._ALLOWED_IMAGE_EXTS):
            await interaction.response.send_message(
                f"❌ Unsupported file type **{image.filename}**. Please upload a PNG, JPG, JPEG, or WEBP image.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)
        guild_id = str(interaction.guild_id)

        event = astra_db_ops.get_clan_event_by_name(guild_id, event_name)
        if not event:
            await interaction.followup.send(f"❌ Event **{event_name}** not found.", ephemeral=True)
            return

        try:
            data = await image.read()
            file = discord.File(io.BytesIO(data), filename=image.filename)

            # Re-post to admin channel to get a stable bot-owned CDN URL.
            # Storing the attachment URL from a bot message is permanent as long
            # as that message exists; user attachment URLs have expiring parameters.
            settings = astra_db_ops.get_clan_event_settings(guild_id)
            admin_ch_id = settings.get("admin_channel_id") if settings else None
            image_url = image.proxy_url  # fallback: Discord-proxied URL

            if admin_ch_id:
                admin_ch = interaction.guild.get_channel(int(admin_ch_id))
                if admin_ch:
                    msg = await admin_ch.send(
                        f"📸 **Event banner — {event_name}** *(do not delete — used in event embeds)*",
                        file=file,
                    )
                    if msg.attachments:
                        image_url = msg.attachments[0].url

            astra_db_ops.update_clan_event_image(guild_id, event["event_id"], image_url)

            embed = discord.Embed(
                title=f"✅ Banner Updated — {event_name}",
                description="The banner has been saved and will appear in event announcements and leaderboards.",
                color=discord.Color.green(),
            )
            embed.set_image(url=image_url)
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logging.error(f"Error setting event banner: {e}")
            await interaction.followup.send("❌ Failed to upload banner. Please try again.", ephemeral=True)

    @event_setbanner.autocomplete("event_name")
    async def _setbanner_event_ac(self, interaction, current):
        return await self._any_event_ac(interaction, current)

    # ---- /event leaderboard ----

    @event_group.command(name="leaderboard", description="View scores and clan rankings")
    @app_commands.describe(
        member="Member to look up (defaults to you)",
        event_name="Specific event (omit for all-time view)",
    )
    @app_commands.guild_only()
    async def event_leaderboard(
        self, interaction: discord.Interaction,
        member: discord.Member = None, event_name: str = None,
    ):
        await interaction.response.defer()
        guild_id = str(interaction.guild_id)
        target = member or interaction.user

        event = event_member_scores = event_clan_scores = None
        alltime_member_scores = alltime_clan_scores = None

        if event_name:
            event = astra_db_ops.get_clan_event_by_name(guild_id, event_name)
            if not event:
                await interaction.followup.send(f"❌ Event **{event_name}** not found.")
                return
            event_member_scores = astra_db_ops.get_clan_event_leaderboard(guild_id, event["event_id"])
            event_clan_scores = astra_db_ops.get_clan_rankings(event_member_scores)
            alltime_member_scores = astra_db_ops.get_clan_alltime_leaderboard(guild_id)
            alltime_clan_scores = astra_db_ops.get_clan_rankings(alltime_member_scores)
        else:
            alltime_member_scores = astra_db_ops.get_clan_alltime_leaderboard(guild_id)
            alltime_clan_scores = astra_db_ops.get_clan_rankings(alltime_member_scores)

        embed = _build_leaderboard_embed(
            target_member=target,
            member_scores=event_member_scores,
            clan_scores=event_clan_scores,
            event=event,
            alltime_member_scores=alltime_member_scores,
            alltime_clan_scores=alltime_clan_scores,
        )
        await interaction.followup.send(embed=embed)

    @event_leaderboard.autocomplete("event_name")
    async def _lb_event_ac(self, interaction, current):
        return await self._any_event_ac(interaction, current)


async def setup(bot: commands.Bot):
    cog = ClanEvents(bot)
    await bot.add_cog(cog)
    cog.daily_recap.start()
