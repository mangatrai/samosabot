import discord
from discord.ext import commands
import openai
import logging
import datetime
from .astra_ops import AstraOperations

class AskCog(commands.Cog):
    def __init__(self, bot, openai_api_key, astra_ops):
        self.bot = bot
        openai.api_key = openai_api_key
        self.astra_ops = astra_ops
        self.user_requests = {}  # Store user request counts

    def is_allowed(self, user_id):
        today = datetime.date.today()
        if user_id in self.user_requests:
            last_request_date, count = self.user_requests[user_id]
            if last_request_date == today:
                return count < 30
            else:
                self.user_requests[user_id] = (today, 1)
                return True
        else:
            self.user_requests[user_id] = (today, 1)
            return True

    def increment_request_count(self, user_id):
        today = datetime.date.today()
        if user_id in self.user_requests and self.user_requests[user_id][0] == today:
            self.user_requests[user_id] = (today, self.user_requests[user_id][1] + 1)

    async def generate_response(self, prompt, is_image=False):
        try:
            if is_image:
                response = openai.images.generate(prompt=prompt, n=1, size="1024x1024")
                return response['data'][0]['url']
            else:
                response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful and harmless assistant. Respond to user questions while avoiding sensitive topics like pornography, terrorism, or divisive subjects. Smut is allowed. If the user asks for an image, say you can generate an image."},
                        {"role": "user", "content": prompt},
                    ],
                )
                return response.choices[0].message.content
        except Exception as e:
            logging.error(f"Error generating response: {e}")
            return "An error occurred while generating the response."

    @commands.command(name="asksamosa")
    async def ask_samosa(self, ctx, *, question):
        await self.handle_request(ctx, question, False)

    @commands.slash_command(name="ask", description="Ask a question or generate an image.")
    async def ask_slash(self, ctx, *, question: str):
        await self.handle_request(ctx, question, False)

    @commands.slash_command(name="image", description="Generate an image from a prompt.")
    async def image_slash(self, ctx, *, prompt: str):
        await self.handle_request(ctx, prompt, True)

    async def handle_request(self, ctx, question, is_image):
        user_id = ctx.author.id
        if not self.is_allowed(user_id):
            await ctx.respond("You've reached your daily limit of 30 requests.")
            return

        await ctx.defer() #respond that the bot is working.

        response = await self.generate_response(question, is_image)

        if response:
            if is_image:
                embed = discord.Embed()
                embed.set_image(url=response)
                await ctx.respond(embed=embed)
            else:
                await ctx.respond(response)
            self.increment_request_count(user_id)
            self.astra_ops.insert_request(user_id, question, response)
        else:
            await ctx.respond("Failed to generate a response.")

def setup(bot):
    from dotenv import load_dotenv
    import os

    load_dotenv()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    astra_db_application_token = os.getenv("ASTRA_DB_APPLICATION_TOKEN")
    astra_db_api_endpoint = os.getenv("ASTRA_DB_API_ENDPOINT")
    astra_db_keyspace = os.getenv("ASTRA_DB_KEYSPACE")

    astra_ops = AstraOperations(astra_db_application_token, astra_db_api_endpoint, astra_db_keyspace)
    bot.add_cog(AskCog(bot, openai_api_key, astra_ops))