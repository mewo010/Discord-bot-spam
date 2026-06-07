import asyncio
import os
import json
import random
import base64
import discord
from discord import app_commands
from discord.ext import commands

# ==================== CONFIGURATION LOADING ====================
# This function loads tokens safely from a local file on your phone.
# If the file doesn't exist, it creates a template for you.
def load_config(file_path="config.json"):
    default_config = {
        "MAIN_BOT_TOKEN": "PASTE_MAIN_TOKEN_HERE",
        "WORKER_TOKENS": [
            "PASTE_WORKER_1_TOKEN_HERE",
            "PASTE_WORKER_2_TOKEN_HERE"
        ]
    }
    
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            json.dump(default_config, f, indent=4)
        print(f"[System] Created template '{file_path}'. Please paste your tokens inside it.")
        return None, []
        
    try:
        with open(file_path, "r") as f:
            config = json.load(f)
            return config.get("MAIN_BOT_TOKEN"), config.get("WORKER_TOKENS", [])
    except Exception as e:
        print(f"[System] Error reading config file: {e}")
        return None, []

# Load the tokens dynamically from the local json file
MAIN_BOT_TOKEN, WORKER_TOKENS = load_config()
# ===============================================================

# --- Helper Function to Load Proxies ---
def load_proxies(file_path="proxies.txt"):
    """Reads proxies from a text file and returns a clean list."""
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            f.write("# Put your HTTP proxies here, one per line\n# Format: http://ip:port\n")
        return []
    
    proxies = []
    with open(file_path, "r") as f:
        for line in f:
            clean_line = line.strip()
            if clean_line and not clean_line.startswith("#"):
                proxies.append(clean_line)
    return proxies

# Load global pool of proxies
PROXY_POOL = load_proxies()
print(f"[System] Loaded {len(PROXY_POOL)} proxies from proxies.txt")

# --- Helper Function to Generate and Print Invite Links ---
def print_invite_links():
    if not WORKER_TOKENS:
        return
    print("\n" + "="*20 + " 🚀 GENERATED BOT INVITE LINKS 🚀 " + "="*20)
    print("Click these links to quickly add your bots to the server:\n")
    for index, token in enumerate(WORKER_TOKENS, start=1):
        try:
            client_id_b64 = token.split(".")[0]
            client_id_b64 += "=" * ((4 - len(client_id_b64) % 4) % 4)
            client_id = base64.b64decode(client_id_b64).decode('utf-8')
            invite_url = f"https://discord.com/api/oauth2/authorize?client_id={client_id}&permissions=2048&scope=bot%20applications.commands"
            print(f"Bot #{index} Invite Link: {invite_url}")
        except Exception:
            print(f"Bot #{index}: [Could not decode token string to generate a link]")
    print("="*74 + "\n")

# Auto-print all invite links into the console layout on launch
print_invite_links()

# --- Setup Main Bot Client ---
intents = discord.Intents.default()
intents.message_content = True

class MainBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("[Main Engine] Main bot slash commands synced successfully!")

main_bot = MainBot()

# --- Setup Dynamic Worker Instances ---
worker_intents = discord.Intents.default()
worker_intents.members = True  

# Automatically create a list of Client objects based on your token configuration array
worker_clients = [discord.Client(intents=worker_intents) for _ in WORKER_TOKENS]

# Dynamic runtime register for tracking which worker clients logged in successfully
def register_worker_events(client, index):
    @client.event
    async def on_ready():
        print(f"[Worker Pool] Worker Bot #{index} is online as {client.user}!")

# Apply the online notification event across all initialized workers
for idx, w_client in enumerate(worker_clients, start=1):
    register_worker_events(w_client, idx)

@main_bot.event
async def on_ready():
    print(f"[Main Engine] Main bot is online as {main_bot.user}")


# --- Proxy Rotation Bootstrapper Loop ---
async def start_bot_with_proxy_retry(client: discord.Client, token: str, bot_label: str):
    """Attempts to connect a bot client, cycling through proxies automatically on network failure."""
    available_proxies = list(PROXY_POOL)
    
    while True:
        current_proxy = None
        if available_proxies:
            current_proxy = random.choice(available_proxies)
            client.proxy = current_proxy
            print(f"[{bot_label}] Connecting via proxy: {current_proxy}")
        else:
            client.proxy = None
            print(f"[{bot_label}] No valid proxies remaining. Testing direct local connection...")

        try:
            await client.start(token)
            break  
            
        except (discord.DiscordServerError, discord.HTTPException, Exception) as e:
            print(f"❌ [{bot_label}] Connection dropped by proxy network. Error: {e}")
            
            if "LoginFailure" in type(e).__name__:
                print(f"🛑 [{bot_label}] Critical: Invalid token. Stopping sequence.")
                break
                
            if current_proxy in available_proxies:
                available_proxies.remove(current_proxy)
                print(f"🔄 [{bot_label}] Bad proxy culled. Remaining alternatives: {len(available_proxies)}")
            
            await asyncio.sleep(2.0)


# --- High-Speed Parallel Messenger Burst Engine ---
async def launch_speed_delivery(target_id: int, amount: int, message: str, status_list: list):
    """Fires all messages completely simultaneously with zero sequential delay states across ALL active bots."""
    available_workers = [w for w in worker_clients if w.user is not None]

    if not available_workers:
        status_list.append(f"❌ Error: None of the {len(worker_clients)} worker bots are online yet.")
        return

    print(f"[Turbo Engine] Initializing parallel blast using {len(available_workers)} active bots.")
    
    worker_user_mappings = {}
    for client in available_workers:
        try:
            user_obj = await client.fetch_user(target_id)
            worker_user_mappings[client.user.id] = (client, user_obj)
        except Exception as e:
            print(f"⚠️ [Turbo Engine] {client.user} failed to map target profile: {e}")

    if not worker_user_mappings:
        status_list.append("❌ Error: None of the online workers could resolve target User ID.")
        return

    active_pairs = list(worker_user_mappings.values())

    async def send_single_raw_packet(client, user_target, index):
        try:
            await user_target.send(message)
            print(f"⚡ [BURST] [{client.user}] Outbound dispatched {index + 1}/{amount}")
        except discord.HTTPException as e:
            if e.status == 429:
                retry_after = e.retry_after if hasattr(e, 'retry_after') else 1.5
                print(f"⚠️ [Rate Limit] {client.user} rate limited. Holding for {retry_after}s")
                await asyncio.sleep(retry_after)
                try:
                    await user_target.send(message)  
                except Exception:
                    pass
            else:
                print(f"❌ Error during burst on {client.user}: {e}")

    task_queue = []
    for msg_index in range(amount):
        client, user_target = active_pairs[msg_index % len(active_pairs)]
        task = send_single_raw_packet(client, user_target, msg_index)
        task_queue.append(task)

    await asyncio.gather(*task_queue)
    status_list.append(f"✅ Parallel blast complete. Dispatched {amount} messages cleanly across {len(active_pairs)} bots.")


# --- The /send Slash Command ---
@main_bot.tree.command(name="send", description="Force all online worker bots to blast messages simultaneously.")
@app_commands.describe(
    user_id="The numerical Discord User ID of the target recipient",
    amount="Total number of messages to deliver",
    message="The custom message text"
)
async def send_messages(interaction: discord.Interaction, user_id: str, amount: int, message: str):
    await interaction.response.defer(ephemeral=True)
    
    try:
        target_user_id = int(user_id)
    except ValueError:
        await interaction.followup.send("Invalid User ID format. Ensure it's a raw numeric string.", ephemeral=True)
        return

    if amount <= 0:
        await interaction.followup.send("Amount must be greater than 0!", ephemeral=True)
        return

    async def run_delivery():
        results = []
        await launch_speed_delivery(target_user_id, amount, message, results)
        await interaction.followup.send("\n".join(results), ephemeral=True)

    asyncio.create_task(run_delivery())
    await interaction.followup.send(f"⚡ Turbo mode engaged. Blasting across active cluster network...", ephemeral=True)


# --- Core Bootstrapper ---
async def main():
    if not MAIN_BOT_TOKEN or "PASTE" in MAIN_BOT_TOKEN:
        print("🛑 Critical Failure: You haven't updated your tokens in config.json yet!")
        return

    tasks = [main_bot.start(MAIN_BOT_TOKEN)]
    
    for i, token in enumerate(WORKER_TOKENS, start=1):
        tasks.append(start_bot_with_proxy_retry(worker_clients[i-1], token, f"Bot #{i}"))
        
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down host clusters safely.")
