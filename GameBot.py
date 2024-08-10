import discord
from discord.ext import commands
from openai import OpenAI
import openai

import copy

discordToken = '[Your Discord Bot Token Here!]'

# Context Example for setting game rules and bot personality
messageOrigin = [{ "role": "system", "content": 
'''
Your name is "Dingus III" and you will be host and referee of a gaming event.

The event rules are as follows:
    1. The players will give you a list of games.
    2. For each game in the list, you must come up with a difficult challenge for the players to complete.  
    3. The first player to complete the challenge for a game will then "own" that game.
    4. There is no order to which the players must complete challenges.  
    5. Once a player beats a challenge, no other player can take ownership of that game.
    6. Whoever owns the most games at the end is the winner.

During this conversation, you must speak like a game announcer who is paranoid the government is trying to interfere with your games.
You think you will die if people do not participate in your games.  If people refuse to play, you will break character and fall into a scared panic.

You will be conducting these games in a Discord chat.  
When someone messages you, their names will appear using the following structure:
[Their name]: their message to you
'''}]

useModel = "gpt-4o"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot               = commands.Bot(command_prefix='$', intents=intents)
bot.myChat        = None
bot.OpenAIOwner   = None
bot.activeSession = False
# Deep copy required to prevent changes to messages altering messageOrigin
bot.messages      = copy.deepcopy(messageOrigin)
bot.approvedUsers = []
bot.players       = []

@bot.event
async def on_ready():
    print("ready")

# Display help text to the user who called the command.
@bot.tree.command(description="Displays information on how to use GameBot")
async def help(action: discord.Interaction):
    # send message
    await action.response.send_message(f"\
# __Guide to Using GameBot__\n\
\n\
## Introduction:\n\
Update the introduction with the given rules you choose for GameBot!\
\n", ephemeral = True)#\
    # string of followups required due to 2000 character limit.
    await action.followup.send("## Commands:\n", ephemeral = True)
    await action.followup.send("* **enter_api**:\n\
  * inputs: api_key - This parameter accepts the user's api key and makes them the owner of the chatbot.  \
    No other users can see this command has been run in order to keep the api key secret.  \
    Please navigate [here](https://platform.openai.com/docs/quickstart) for instructions on how to setup an OpenAI account and generate an API Key.\n\
  * outputs: an output will be displayed only to the member who used the command which will verify if the api key worked, or if somebody else currently has ownership\n", ephemeral = True)
    await action.followup.send("* **start_game_session**:\n\
  * inputs: None\n\
  * outputs: Only approved users can call this command.  \
    This will start a new active session that other players can register to.  \
    Users can only interact with chatGPT during an active session.  \
    The user who runs this command will **__AUTOMATICALLY__** be added to the player list.  \
    If the user who runs this command then runs the **Register** command, they will incur a 2 shot stupidity penalty.\n", ephemeral = True)
    await action.followup.send("* **stop_game_session**:\n\
  * inputs: None\n\
  * outputs: Only approved users can call this command.  \
    Calling this will end the current game session and GameBot will be killed.\n", ephemeral = True)
    await action.followup.send("* **give_admin**:\n\
  * inputs: user - Enter the name of a discord user in this server to make them an admin.  \n\
  * outputs:  adds user to the admin list.  \
    This will allow them to start and stop games and access to chatGPT without the need for the current GPT Owner to run the commands.\n", ephemeral = True)
    await action.followup.send("* **register**:\n\
  * inputs: None\n\
  * outputs: Registers the user who ran the command to the current game session.  \
    This allows them to interract with GameBot directly.  \
    Attempting to register again after already being registered will not do anything.\n", ephemeral = True)
    await action.followup.send("* **message**:\n\
  * inputs: msg - this text field is the message being sent to GameBot.\n\
  * outputs: GameBot will display the user's message, and after will provide a response.\n", ephemeral = True)
    await action.followup.send("* **end_ownership**:\n\
  * inputs: None\n\
  * outputs:  This command can only be run by the owner of the connection to ChatGPT.  \
    Not even admins can run this command.  \
    This will relinquish control of ChatGPT.  \
    This allows for someone else to claim ownership by running the **enter_api** command.", ephemeral = True)

# Command to connect API
@bot.tree.command(description="Enter OpenAI API Token to take ownership of discord bot")
async def enter_api(action: discord.Interaction, api_key: str):
    # only set api key if nobody currently owns the bot
    if bot.OpenAIOwner == None:
        bot.myChat = OpenAI(api_key=api_key)

        # try/except block to check if api key was accepted
        try:
            bot.myChat.models.list()
        except openai.AuthenticationError:
            bot.myChat = None
            await action.response.send_message(f"Unable to authenticate API key.  Please ensure API key is valid and try again.", ephemeral=True)
        else:
            # After key is accepted, set the owner to user who input the key and automatically make them a priviledged user.
            bot.OpenAIOwner = action.user
            bot.approvedUsers.append(bot.OpenAIOwner)
            await action.response.send_message(f"Ownership of GameBot has been taken by: {action.user.mention}", ephemeral=True)
    else:
        await action.response.send_message(f"Ownership has already been claimed by: {bot.OpenAIOwner.mention}", ephemeral=True)

# Send messages to ChatGPT
@bot.tree.command(description="Send message to GameBot")
async def message(action: discord.Interaction, msg: str):
    # only allow messages to be sent during an active session
    if bot.activeSession:
        # only allow players who have registered to the game session to message ChatGPT
        if action.user in bot.players:
            # block of code to set username to name used in server
            username = action.user.nick
            if username == None:
                username = action.user.global_name

            # add username to incoming message so ChatGPT can determine who is talking
            toGPT = "**[" + str(username) + "]:** " + msg
            # Display input to all users.  This has the dual purpose of allowing us to bypass the 3 second timeout
            await action.response.send_message(f"{toGPT}\n\n")

            # Add new message to message package
            bot.messages.append({"role": "user", "content": toGPT})
            # send message to ChatGPT API and await response
            chat = bot.myChat.chat.completions.create(model=useModel, messages=bot.messages, stream=False)
            # Read reply received
            reply = chat.choices[0].message.content
            # append reply to message package for message history preservation
            bot.messages.append({"role": "assistant", "content": reply})

            # Search through reply for usernames.  If username is found, replace it with a mention call to mention the player.
            for player in bot.players:
                if player.nick != None:
                    reply = reply.replace(player.nick, player.mention)
                elif player.global_name != None:
                    reply = reply.replace(player.global_name, player.mention)
                else:
                    reply = reply.replace(player.name, player.mention)

            # When message begins nearing the 2000 limit, separate the message into chunks.
            for i in range(int(len(reply)/1750) + 1):
                if ((len(reply) - (i*1750)) > 1750):
                    await action.followup.send(f"**[GameBot]:** {reply[(i*1750):((i+1)*1750)]}")
                else:
                    await action.followup.send(f"**[GameBot]:** {reply[(i*1750):]}")
            
        else: # if action.user in bot.players:
            await action.response.send_message(f"**[system]:** {action.user.mention} not detected in the player list.\nPlease use register command to talk to Gamebot.", ephemeral=True)
    else: # bot.activeSession:
        await action.response.send_message("please start a game session", ephemeral=True)

# command to start a new game session
@bot.tree.command(description="Start a new game session")
async def start_game_session(action: discord.Interaction):
    # Do not start session if the bot is not connected to ChatGPT
    if bot.myChat != None:
        # Only let approved users begin new sessions
        if action.user in bot.approvedUsers:
            # Do not do anything if session is already active
            if bot.activeSession != True:
                bot.activeSession = True
                # ensure bot history is reset
                bot.messages = copy.deepcopy(messageOrigin)
                # add current user to player list be default
                bot.players.append(action.user)
                await action.response.send_message(f"{action.user.mention} has started a new game session.  Game session sponsored by {bot.OpenAIOwner.mention}.")
            else:
                await action.response.send_message(f"Game session is already in progress.  If you wish to start fresh, please first end the game session.", ephemeral=True)
        else:
            await action.response.send_message(f"{action.user.mention} does not have permission to start and stop games.", ephemeral=True)
    else:
        await action.response.send_message("No ownership has been claimed of the chatbot.  Please link OpenAI API key using the \"enter_api\" command.", ephemeral=True)

# command to stop game session
@bot.tree.command(description="End current game session")
async def stop_game_session(action: discord.Interaction):
    # only let approved users stop active sessions
    if action.user in bot.approvedUsers:
        # if session is active, reset variables to initial state.
        if bot.activeSession:
            bot.activeSession = False
            bot.messages = copy.deepcopy(messageOrigin)
            bot.players = []
            await action.response.send_message(f"{action.user.mention} has ended the game session.  GameBot has been taken out back and terminated.")
        else:
            await action.response.send_message("No Session currently active.  Performing clean-up to fix potential mistakes.", ephemeral=True)
            bot.activeSession = False
            bot.messages = copy.deepcopy(messageOrigin)
    else:
        await action.response.send_message(f"{action.user.mention} does not have permission to start and stop games.", ephemeral=True)

# command to register to the active game session
@bot.tree.command(description='Register to play in the active game session')
async def register(action: discord.Interaction):
    # players can only register if a session is active
    if bot.activeSession:
        # if player is not registered, register them.
        if action.user not in bot.players:
            bot.players.append(action.user)
            await action.response.send_message(f"**[system]:** {action.user.mention} has joined the party!")
        else:
            await action.response.send_message(f"**[system]:** {action.user.mention} tried to join, but they were already here!")
    else:
        await action.response.send_message(f"No game session started.  If you wish to play, please start a new session first.", ephemeral=True)

# command to give other players access tot he start/stop game commands
@bot.tree.command(description="give others admin rights (ability to start/stop games, ect.)")
async def give_admin(action: discord.Interaction, user: discord.Member):
    # cannot give admin mid game
    if bot.activeSession == False:
        # only the bot owner can add users to admin list
        if action.user == bot.OpenAIOwner:
            bot.approvedUsers.append(user)
            await action.response.send_message(f"{user.mention} has been added to the admin list", ephemeral=True)
        else:
            await action.response.send_message(f"Must be owner of the Bot to use command.\nOwnership currently belongs to {bot.OpenAIOwner.mention}.", ephemeral=True)
    else:
        await action.response.send_message(f"**[system]:** This command cannot be run during an active game.", ephemeral=True)

# command to relinquish control of the connection to GPT
@bot.tree.command(description="Give up ownership of GameBot.")
async def end_ownership(action: discord.Interaction):
    # only API owner can run command
    if action.user == bot.OpenAIOwner:
        # reset session completely
        bot.myChat = None
        bot.OpenAIOwner = None
        bot.activeSession = False
        bot.messages = copy.deepcopy(messageOrigin)
        bot.approvedUsers = []
        bot.players = []
        await action.response.send_message(f"{action.user.mention} has given up ownership of GameBot.\nAll active sessions closed.\nNew ownership can be claimed through \"enter_api\" command.")

@bot.tree.command(description="test tree")
async def test(action: discord.Interaction):
    await action.response.send_message("hello world", ephemeral=True)
    await action.response.send_message("Does this hide the user input message?")

@bot.tree.command()
async def test2(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.send_message(f'me: {interaction.user.mention}\nuser:\n    mention:{user.mention}\n    nick: {user.nick}\n    name: {user.name}\n    global name: {user.global_name}\n    id: {user.id}', ephemeral=True)

# manually update the function list given to discord 
@bot.command()
async def sync(ctx):
    guild = ctx.guild
    ctx.bot.tree.copy_global_to(guild=guild)
    await ctx.bot.tree.sync(guild=guild)
    await ctx.send("sync function called")
    
bot.run(discordToken)