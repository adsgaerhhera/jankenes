import discord
from discord.ext import commands
import asyncio
import random
from dotenv import load_dotenv
import os

# 環境変数の読み込み
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))

# Discord Botの準備
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# じゃんけんゲームコマンド
@bot.command()
async def janken(ctx, role: discord.Role = None):
    participants = []

    if role is None:
        # 参加するかどうか選ぶメッセージを送る
        await ctx.send("じゃんけんを始めます！参加するかどうか選んでください！\n参加する場合はこのメッセージにリアクションをつけてください。")
        
        # 参加するかどうかのリアクション
        reaction_emoji = "✅"  # 参加するリアクション
        await ctx.message.add_reaction(reaction_emoji)

        def check(reaction, user):
            return str(reaction.emoji) == reaction_emoji and not user.bot

        # 15秒間、リアクションを待つ
        await bot.wait_for("reaction_add", timeout=15.0, check=check)
        
        # リアクションしたユーザーを参加者として追加
        participants = [user for user in ctx.guild.members if str(reaction_emoji) in [str(reaction.emoji) for reaction in await ctx.message.reactions]]
        if not participants:
            await ctx.send("参加者がいません。終了します。")
            return
        await ctx.send(f"参加者: {', '.join([member.display_name for member in participants])}")
    else:
        # 参加するメンバーをロールでフィルタリング
        participants = [member for member in ctx.guild.members if role in member.roles and not member.bot]
        if not participants:
            await ctx.send(f"指定したロール「{role.name}」を持つユーザーは参加できませんでした。")
            return
        await ctx.send(f"じゃんけんを始めます！参加者: {', '.join([member.display_name for member in participants])}")

    hand_map = {"👊": "グー", "✌️": "チョキ", "✋": "パー"}
    reactions = ["👊", "✌️", "✋"]

    # ボットを参加させる
    participants.append(bot.user)

    # 参加者に手を選ばせるDMを送る
    player_choices = {}

    for player in participants:
        try:
            # DMメッセージを送る
            dm_message = await player.send(
                "じゃんけんの手をリアクションで選んでください！\n"
                "👊: グー\n"
                "✌️: チョキ\n"
                "✋: パー"
            )
            for reaction in reactions:
                await dm_message.add_reaction(reaction)

            # リアクションが追加されるのを待つ
            def check(reaction, user):
                return user == player and str(reaction.emoji) in reactions

            reaction, _ = await bot.wait_for("reaction_add", timeout=10.0, check=check)
            player_choices[player.id] = str(reaction.emoji)
            await player.send(f"あなたの選択: {reaction.emoji} ({hand_map[reaction.emoji]}) を受け付けました！")
        except asyncio.TimeoutError:
            await player.send("時間切れです。手の選択ができませんでした。")
        except discord.Forbidden:
            await ctx.send(f"{player.display_name}さんにはDMが送れませんでした。")

    # ボットの手をランダムで決定
    bot_choice = random.choice(reactions)
    player_choices[bot.user.id] = bot_choice
    await ctx.send(f"ボットの手は {hand_map[bot_choice]} です！")

    # 勝敗を判定
    win_table = {"👊": "✌️", "✌️": "✋", "✋": "👊"}
    results_message = "各プレイヤーの選択:\n"
    for player_id, player_choice in player_choices.items():
        player = await bot.fetch_user(player_id)
        results_message += f"- {player.display_name}: {hand_map[player_choice]}\n"

    # あいこの判定
    if len(set(player_choices.values())) == 1:
        results_message += "\n**あいこ（引き分け）です！**"
    elif len(set(player_choices.values())) == 3:
        results_message += "\n**あいこ（引き分け）です！**"
    else:
        results_message += "\n"
        winners = []
        for player_id, player_choice in player_choices.items():
            for opponent_id, opponent_choice in player_choices.items():
                if player_id != opponent_id:
                    if win_table[player_choice] == opponent_choice:
                        winners.append(player_id)

        if winners:
            results_message += "**勝者:**\n"
            for winner_id in winners:
                winner = await bot.fetch_user(winner_id)
                results_message += f"- {winner.display_name}\n"

            losers = [player_id for player_id in player_choices.keys() if player_id not in winners and player_id != bot.user.id]
            if losers:
                results_message += "\n**敗者:**\n"
                for loser_id in losers:
                    loser = await bot.fetch_user(loser_id)
                    results_message += f"- {loser.display_name}\n"

    await ctx.send(results_message)

bot.run(TOKEN)
