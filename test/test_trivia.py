import asyncio
import discord
from discord.ext import commands
import os
import sys
from datetime import datetime
import logging
from dotenv import load_dotenv

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from games.trivia_game import start_trivia, stop_trivia

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'trivia_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)

# Load environment variables
load_dotenv()

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Simulated users
class SimulatedUser:
    def __init__(self, name, id):
        self.display_name = name
        self.id = id
        self.guild_id = 123456789  # Test guild ID
        self.answers = []  # Track user's answers
        self.correct_count = 0
        self.wrong_count = 0

# Create simulated users
users = [
    SimulatedUser("Player1", 1001),
    SimulatedUser("Player2", 1002),
    SimulatedUser("Player3", 1003),
    SimulatedUser("Player4", 1004),
    SimulatedUser("Player5", 1005),  # Added for more test cases
]

# Simulated context
class SimulatedContext:
    def __init__(self, user):
        self.author = user
        self.guild_id = user.guild_id
        self.guild = type('Guild', (), {'id': user.guild_id})()
        
        # Make send an async function that handles embeds and views
        async def send(content=None, *, embed=None, view=None):
            if embed:
                logging.info(f"Bot: [Embed] {embed.title if embed.title else 'No title'}")
                if embed.description:
                    logging.info(f"Description: {embed.description}")
                for field in embed.fields:
                    logging.info(f"Field: {field.name} = {field.value}")
            elif content:
                logging.info(f"Bot: {content}")
            if view:
                logging.info("View attached with buttons")
                # Store the view for later interaction
                self.current_view = view
            return type('Message', (), {})()
        self.send = send
        
        # Make channel.send an async function that handles embeds and views
        async def channel_send(content=None, *, embed=None, view=None):
            if embed:
                logging.info(f"Channel: [Embed] {embed.title if embed.title else 'No title'}")
                if embed.description:
                    logging.info(f"Description: {embed.description}")
                for field in embed.fields:
                    logging.info(f"Field: {field.name} = {field.value}")
            elif content:
                logging.info(f"Channel: {content}")
            if view:
                logging.info("View attached with buttons")
                # Store the view for later interaction
                self.current_view = view
            return type('Message', (), {})()
        self.channel = type('Channel', (), {'send': channel_send})()
        
        # Make response methods async
        async def response_send_message(content=None, *, embed=None, ephemeral=False):
            if embed:
                logging.info(f"Response: [Embed] {embed.title if embed.title else 'No title'}")
                if embed.description:
                    logging.info(f"Description: {embed.description}")
                for field in embed.fields:
                    logging.info(f"Field: {field.name} = {field.value}")
            elif content:
                logging.info(f"Response: {content}")
            return type('Message', (), {})()
            
        async def response_defer():
            logging.info("Response deferred")
            
        async def followup_send(content=None, *, embed=None):
            if embed:
                logging.info(f"Followup: [Embed] {embed.title if embed.title else 'No title'}")
                if embed.description:
                    logging.info(f"Description: {embed.description}")
                for field in embed.fields:
                    logging.info(f"Field: {field.name} = {field.value}")
            elif content:
                logging.info(f"Followup: {content}")
            return type('Message', (), {})()
            
        self.response = type('Response', (), {
            'send_message': response_send_message,
            'defer': response_defer,
            'followup': type('Followup', (), {
                'send': followup_send
            })()
        })()

async def simulate_button_interaction(ctx, user, answer):
    """Simulate a user clicking a button"""
    if hasattr(ctx, 'current_view'):
        for item in ctx.current_view.children:
            if isinstance(item, discord.ui.Button):
                if item.custom_id == f"answer_{answer}":
                    # Create a simulated interaction
                    interaction = type('Interaction', (), {
                        'user': user,
                        'response': type('Response', (), {
                            'edit_message': lambda view=None: logging.info(f"Button {answer} clicked by {user.display_name}")
                        })()
                    })()
                    await item.callback(interaction)
                    break

async def simulate_scenario_1():
    """Scenario 1: Normal gameplay with mixed correct/incorrect answers"""
    logging.info("\n=== Starting Scenario 1: Normal Gameplay ===")
    
    ctx = SimulatedContext(users[0])
    await start_trivia(ctx, "general", bot, num_questions=3, is_slash=False)
    
    for i in range(3):
        logging.info(f"\nQuestion {i+1}:")
        for user in users:
            # Simulate user answering
            correct = (user.id % 2 == 0)  # Even IDs answer correctly
            answer = "A" if correct else "B"  # Simulate answer selection
            await simulate_button_interaction(ctx, user, answer)
            logging.info(f"{user.display_name} answers {'correctly' if correct else 'incorrectly'}")
            if correct:
                user.correct_count += 1
            else:
                user.wrong_count += 1
            await asyncio.sleep(2)
        
        logging.info("Waiting for question timeout...")
        await asyncio.sleep(35)

async def simulate_scenario_2():
    """Scenario 2: Quick answers with all correct responses"""
    logging.info("\n=== Starting Scenario 2: All Correct Answers ===")
    
    ctx = SimulatedContext(users[0])
    await start_trivia(ctx, "general", bot, num_questions=2, is_slash=False)
    
    for i in range(2):
        logging.info(f"\nQuestion {i+1}:")
        for user in users:
            # Simulate user answering correctly
            await simulate_button_interaction(ctx, user, "A")
            logging.info(f"{user.display_name} answers correctly")
            user.correct_count += 1
            await asyncio.sleep(1)  # Faster responses
        
        logging.info("Waiting for question timeout...")
        await asyncio.sleep(35)

async def simulate_scenario_3():
    """Scenario 3: Edge cases - late answers and no answers"""
    logging.info("\n=== Starting Scenario 3: Edge Cases ===")
    
    ctx = SimulatedContext(users[0])
    await start_trivia(ctx, "general", bot, num_questions=2, is_slash=False)
    
    for i in range(2):
        logging.info(f"\nQuestion {i+1}:")
        # Only first two users answer
        for user in users[:2]:
            correct = (user.id % 2 == 0)
            answer = "A" if correct else "B"
            await simulate_button_interaction(ctx, user, answer)
            logging.info(f"{user.display_name} answers {'correctly' if correct else 'incorrectly'}")
            if correct:
                user.correct_count += 1
            else:
                user.wrong_count += 1
            await asyncio.sleep(2)
        
        # Last user answers very late
        await asyncio.sleep(25)  # Late answer
        await simulate_button_interaction(ctx, users[-1], "B")
        logging.info(f"{users[-1].display_name} answers very late")
        users[-1].wrong_count += 1
        
        logging.info("Waiting for question timeout...")
        await asyncio.sleep(10)

async def simulate_scenario_4():
    """Scenario 4: Game interruption and stop"""
    logging.info("\n=== Starting Scenario 4: Game Interruption ===")
    
    ctx = SimulatedContext(users[0])
    await start_trivia(ctx, "general", bot, num_questions=3, is_slash=False)
    
    # Simulate one question
    logging.info("\nQuestion 1:")
    for user in users[:2]:
        correct = (user.id % 2 == 0)
        answer = "A" if correct else "B"
        await simulate_button_interaction(ctx, user, answer)
        logging.info(f"{user.display_name} answers {'correctly' if correct else 'incorrectly'}")
        if correct:
            user.correct_count += 1
        else:
            user.wrong_count += 1
        await asyncio.sleep(2)
    
    # Stop the game early
    logging.info("\nStopping game early...")
    await stop_trivia(ctx, users[0].guild_id, bot, is_slash=False)

async def simulate_scenario_5():
    """Scenario 5: Multiple games in sequence"""
    logging.info("\n=== Starting Scenario 5: Multiple Games ===")
    
    for game_num in range(2):
        logging.info(f"\nStarting Game {game_num + 1}")
        ctx = SimulatedContext(users[0])
        await start_trivia(ctx, "general", bot, num_questions=2, is_slash=False)
        
        for i in range(2):
            logging.info(f"\nQuestion {i+1}:")
            for user in users:
                correct = (user.id % 2 == 0)
                answer = "A" if correct else "B"
                await simulate_button_interaction(ctx, user, answer)
                logging.info(f"{user.display_name} answers {'correctly' if correct else 'incorrectly'}")
                if correct:
                    user.correct_count += 1
                else:
                    user.wrong_count += 1
                await asyncio.sleep(2)
            
            logging.info("Waiting for question timeout...")
            await asyncio.sleep(35)
        
        # Wait between games
        await asyncio.sleep(5)

async def main():
    try:
        logging.info("Starting trivia game test suite...")
        
        # Run all scenarios
        await simulate_scenario_1()
        await simulate_scenario_2()
        await simulate_scenario_3()
        await simulate_scenario_4()
        await simulate_scenario_5()
        
        # Print final statistics
        logging.info("\n=== Final Statistics ===")
        for user in users:
            logging.info(f"{user.display_name}: ✅ {user.correct_count} | ❌ {user.wrong_count}")
        
        logging.info("\nTest suite completed successfully!")
        
    except Exception as e:
        logging.error(f"Error during test: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main()) 