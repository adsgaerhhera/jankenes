import discord
from discord.ext import commands
import asyncio
import random
from dotenv import load_dotenv
import os
from flask import Flask
import threading

# 環境変数の読み込み
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))

# Discord Botの準備
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.voice_states = True  # ボイスチャットの状態変更を取得
bot = commands.Bot(command_prefix="!", intents=intents)

# Flaskアプリケーション（ヘルスチェック用）
app = Flask("")

@app.route("/")
def home():
    return "Bot is running!", 200  # ヘルスチェック用レスポンス

def run_http_server():
    # Koyebで提供されるPORT環境変数を使用
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    threading.Thread(target=run_http_server).start()

# じゃんけんゲームコマンド
@bot.command()
async def janken(ctx, target_role: discord.Role = None):
    participants = []

    if target_role:
        # 指定したロールを持っているメンバー全員にDMを送る
        for member in ctx.guild.members:
            if target_role in member.roles and not member.bot:
                participants.append(member)
                try:
                    dm_message = await member.send(
                        "じゃんけんの手をリアクションで選んでください！\n"
                        "👊: グー\n"
                        "✌️: チョキ\n"
                        "✋: パー"
                    )
                    for reaction in ["👊", "✌️", "✋"]:
                        await dm_message.add_reaction(reaction)
                except discord.Forbidden:
                    print(f"{member.name}にDMを送れませんでした。")
    else:
        # 参加者募集メッセージを送る
        msg = await ctx.send("じゃんけんに参加するにはこのメッセージにリアクションしてください！")

        # 参加ボタンとしてのリアクションを追加
        await msg.add_reaction("✅")  # 参加するには✅を押す

        def check(reaction, user):
            return user != bot.user and str(reaction.emoji) == "✅"  # リアクションが✅の場合のみ

        try:
            # リアクションを待つ (最大15秒)
            reaction, user = await bot.wait_for("reaction_add", timeout=15.0, check=check)
            participants.append(user)
            await ctx.send(f"{user.display_name} が参加しました！")
        except asyncio.TimeoutError:
            await ctx.send("参加者がいませんでした。")

    # ボットを参加させる
    participants.append(bot.user)

    # 参加者にDMで手を選ばせる
    reactions = ["👊", "✌️", "✋"]
    hand_map = {"👊": "グー", "✌️": "チョキ", "✋": "パー"}

    async def send_dm_and_wait(player):
        try:
            dm_message = await player.send(
                "じゃんけんの手をリアクションで選んでください！\n"
                "👊: グー\n"
                "✌️: チョキ\n"
                "✋: パー"
            )
            for reaction in reactions:
                await dm_message.add_reaction(reaction)

            def check(reaction, user):
                return user == player and str(reaction.emoji) in reactions

            reaction, user = await bot.wait_for("reaction_add", timeout=30.0, check=check)
            player_choices[player.id] = str(reaction.emoji)
            await player.send(f"あなたの選択: {reaction.emoji} ({hand_map[reaction.emoji]}) を受け付けました！")
        except asyncio.TimeoutError:
            await player.send("時間切れです。手の選択ができませんでした。")

    player_choices = {}
    tasks = []
    for player in participants:
        tasks.append(send_dm_and_wait(player))

    await asyncio.gather(*tasks)

    # ボットの手を選ぶ
    bot_choice = random.choice(reactions)
    player_choices[bot.user.id] = bot_choice
    await ctx.send(f"ボットの手は {hand_map[bot_choice]} です！")

    # 勝敗の決定
    win_table = {"👊": "✌️", "✌️": "✋", "✋": "👊"}
    results_message = "各プレイヤーの選択:\n"
    results = {player_id: {"wins": 0, "losses": 0} for player_id in player_choices.keys()}

    for player_id, player_choice in player_choices.items():
        for opponent_id, opponent_choice in player_choices.items():
            if player_id != opponent_id:
                if win_table[player_choice] == opponent_choice:
                    results[player_id]["wins"] += 1
                elif win_table[opponent_choice] == player_choice:
                    results[player_id]["losses"] += 1

    winners = [player_id for player_id, result in results.items() if result["wins"] > 0 and result["losses"] == 0]
    losers = [player_id for player_id, result in results.items() if result["losses"] > 0 and result["wins"] == 0]

    for player_id, player_choice in player_choices.items():
        player = await bot.fetch_user(player_id)
        results_message += f"- {player.display_name}: {hand_map[player_choice]}\n"

    if winners:
        results_message += "\n**勝者:**\n"
        for winner_id in winners:
            winner = await bot.fetch_user(winner_id)
            results_message += f"- {winner.display_name}\n"

    if losers:
        results_message += "\n**敗者:**\n"
        for loser_id in losers:
            loser = await bot.fetch_user(loser_id)
            results_message += f"- {loser.display_name}\n"

    await ctx.send("結果:\n" + results_message)

# HTTPサーバーを起動しつつ、Discord Botを実行
keep_alive()
bot.run(TOKEN)
