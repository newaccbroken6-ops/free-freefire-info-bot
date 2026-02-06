import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
from datetime import datetime
import json
import os
import asyncio
import io
import uuid
import gc
from datetime import datetime

CONFIG_FILE = "info_channels.json"


class InfoCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.api_url = "https://api-info-v1.vercel.app/check"
        self.generate_url = "http://profile.thug4ff.com/api/profile"
        self.session = aiohttp.ClientSession()
        self.config_data = self.load_config()
        self.cooldowns = {}

   

    

    def convert_unix_timestamp(self, timestamp) -> str:
        try:
            if timestamp and str(timestamp).isdigit():
                return datetime.utcfromtimestamp(int(timestamp)).strftime('%Y-%m-%d %H:%M:%S')
            else:
                return str(timestamp) if timestamp else 'Not available'
        except (ValueError, TypeError):
            return str(timestamp) if timestamp else 'Not available'



    def check_request_limit(self, guild_id):
        try:
            return self.is_server_subscribed(guild_id) or not self.is_limit_reached(guild_id)
        except Exception as e:
            print(f"Error checking request limit: {e}")
            return False

    def load_config(self):
        default_config = {
            "servers": {},
            "global_settings": {
                "default_all_channels": False,
                "default_cooldown": 30,
                "default_daily_limit": 30
            }
        }

        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    loaded_config = json.load(f)
                    loaded_config.setdefault("global_settings", {})
                    loaded_config["global_settings"].setdefault("default_all_channels", False)
                    loaded_config["global_settings"].setdefault("default_cooldown", 30)
                    loaded_config["global_settings"].setdefault("default_daily_limit", 30)
                    loaded_config.setdefault("servers", {})
                    return loaded_config
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading config: {e}")
                return default_config
        return default_config

    def save_config(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=4, ensure_ascii=False)
        except IOError as e:
            print(f"Error saving config: {e}")



    async def is_channel_allowed(self, ctx):
        try:
            guild_id = str(ctx.guild.id)
            allowed_channels = self.config_data["servers"].get(guild_id, {}).get("info_channels", [])

            # Autoriser tous les salons si aucun salon n'a été configuré pour ce serveur
            if not allowed_channels:
                return True

            # Sinon, vérifier si le salon actuel est dans la liste autorisée
            return str(ctx.channel.id) in allowed_channels
        except Exception as e:
            print(f"Error checking channel permission: {e}")
            return False

    @commands.hybrid_command(name="setinfochannel", description="Allow a channel for !info commands")
    @commands.has_permissions(administrator=True)
    async def set_info_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        guild_id = str(ctx.guild.id)
        self.config_data["servers"].setdefault(guild_id, {"info_channels": [], "config": {}})
        if str(channel.id) not in self.config_data["servers"][guild_id]["info_channels"]:
            self.config_data["servers"][guild_id]["info_channels"].append(str(channel.id))
            self.save_config()
            await ctx.send(f"✅ {channel.mention} is now allowed for `!info` commands")
        else:
            await ctx.send(f"ℹ️ {channel.mention} is already allowed for `!info` commands")

    @commands.hybrid_command(name="removeinfochannel", description="Remove a channel from !info commands")
    @commands.has_permissions(administrator=True)
    async def remove_info_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        guild_id = str(ctx.guild.id)
        if guild_id in self.config_data["servers"]:
            if str(channel.id) in self.config_data["servers"][guild_id]["info_channels"]:
                self.config_data["servers"][guild_id]["info_channels"].remove(str(channel.id))
                self.save_config()
                await ctx.send(f"✅ {channel.mention} has been removed from allowed channels")
            else:
                await ctx.send(f"❌ {channel.mention} is not in the list of allowed channels")
        else:
            await ctx.send("ℹ️ This server has no saved configuration")

    @commands.hybrid_command(name="infochannels", description="List allowed channels")
    async def list_info_channels(self, ctx: commands.Context):
        guild_id = str(ctx.guild.id)

        if guild_id in self.config_data["servers"] and self.config_data["servers"][guild_id]["info_channels"]:
            channels = []
            for channel_id in self.config_data["servers"][guild_id]["info_channels"]:
                channel = ctx.guild.get_channel(int(channel_id))
                channels.append(f"• {channel.mention if channel else f'ID: {channel_id}'}")

            embed = discord.Embed(
                title="Allowed channels for !info",
                description="\n".join(channels),
                color=discord.Color.blue()
            )
            cooldown = self.config_data["servers"][guild_id]["config"].get("cooldown", self.config_data["global_settings"]["default_cooldown"])
            embed.set_footer(text=f"Current cooldown: {cooldown} seconds")
        else:
            embed = discord.Embed(
                title="Allowed channels for !info",
                description="All channels are allowed (no restriction configured)",
                color=discord.Color.blue()
            )

        await ctx.send(embed=embed)

    @commands.hybrid_command(name="info", description="Displays information about a Free Fire player")
    @app_commands.describe(uid="FREE FIRE INFO")
    async def player_info(self, ctx: commands.Context, uid: str):
        guild_id = str(ctx.guild.id)

        if not uid.isdigit() or len(uid) < 6:
            return await ctx.reply(" Invalid UID! It must:\n- Be only numbers\n- Have at least 6 digits", mention_author=False)

        if not await self.is_channel_allowed(ctx):
            return await ctx.send(" This command is not allowed in this channel.", ephemeral=True)

        cooldown = self.config_data["global_settings"]["default_cooldown"]
        if guild_id in self.config_data["servers"]:
            cooldown = self.config_data["servers"][guild_id]["config"].get("cooldown", cooldown)

        if ctx.author.id in self.cooldowns:
            last_used = self.cooldowns[ctx.author.id]
            if (datetime.now() - last_used).seconds < cooldown:
                remaining = cooldown - (datetime.now() - last_used).seconds
                return await ctx.send(f" Please wait {remaining}s before using this command again", ephemeral=True)

        self.cooldowns[ctx.author.id] = datetime.now()
       
        try:
            async with ctx.typing():
                async with self.session.get(f"https://api-info-v1.vercel.app/check?uid={uid}") as response:
                    if response.status == 404:
                        return await ctx.send(f" Player with UID `{uid}` not found.")
                    if response.status != 200:
                        return await ctx.send("API error. Try again later.")
                    data = await response.json()
            
            # Extract data from the new API format
            if 'formatted_response' in data or 'raw_api_response' in data:
                formatted_response = data.get('formatted_response', {})
                raw_api_response = data.get('raw_api_response', {})
                responding_region = data.get('responding_region', 'Unknown')
                
                # Extract basic info
                basic_info = raw_api_response.get('basicInfo', {})
                clan_info = raw_api_response.get('clanBasicInfo', {})
                credit_score_info = raw_api_response.get('creditScoreInfo', {})
                pet_info = raw_api_response.get('petInfo', {})
                profile_info = raw_api_response.get('profileInfo', {})
                social_info = raw_api_response.get('socialInfo', {})
                
                # Get values with fallbacks
                nickname = formatted_response.get('nickname', basic_info.get('nickname', 'Not found'))
                region = formatted_response.get('region', basic_info.get('region', 'Not found'))
                level = basic_info.get('level', 'Not found')
                exp = basic_info.get('exp', '?')
                liked = basic_info.get('liked', 'Not found')
                honor_score = credit_score_info.get('creditScore', 'Not found')
                signature = social_info.get('signature', 'None')
                release_version = basic_info.get('releaseVersion', '?')
                badge_count = basic_info.get('badgeCnt', 'Not found')
                br_rank_points = basic_info.get('rankingPoints', '?')
                cs_rank_points = basic_info.get('csRankingPoints', '?')
                created_at = basic_info.get('createAt', 'Not found')
                last_login = basic_info.get('lastLoginAt', 'Not found')
                avatar_id = profile_info.get('avatarId', 'Not found')
                banner_id = basic_info.get('bannerId', 'Not found')
                account_type = basic_info.get('accountType', '?')
                title = basic_info.get('title', 'Not found')
                max_rank = basic_info.get('maxRank', '?')
                current_rank = basic_info.get('rank', '?')
                
                # Pet info
                pet_name = pet_info.get('id', 'Not Found')
                pet_exp = pet_info.get('exp', 'Not Found')
                pet_level = pet_info.get('level', 'Not Found')
                pet_equipped = pet_info.get('isSelected', False)
                pet_skin_id = pet_info.get('skinId', 'Not Found')
                pet_skill_id = pet_info.get('selectedSkillId', 'Not Found')
                
                # Profile info
                equipped_skills = profile_info.get('equipedSkills', 'Not found')
                clothes = profile_info.get('clothes', [])
                skin_color = profile_info.get('skinColor', 'Not found')
                is_selected_awaken = profile_info.get('isSelectedAwaken', False)
                
                # Social info
                gender = social_info.get('gender', 'Not found')
                language = social_info.get('language', 'Not found')
                rank_show = social_info.get('rankShow', 'Not found')
                time_active = social_info.get('timeActive', 'Not found')
                
                # Clan info
                clan_name = clan_info.get('clanName', 'Not found')
                clan_id = clan_info.get('clanId', 'Not found')
                clan_level = clan_info.get('clanLevel', 'Not found')
                clan_members = clan_info.get('memberNum', 'Not found')
                clan_capacity = clan_info.get('capacity', '?')
                clan_captain_id = clan_info.get('captainId', 'Not found')
                
                # Diamond cost
                diamond_cost = raw_api_response.get('diamondCostRes', {}).get('diamondCost', '?')
                
            else:
                # Fallback to old structure
                basic_info = data.get('basicInfo', {})
                clan_info = data.get('clanBasicInfo', {})
                credit_score_info = data.get('creditScoreInfo', {})
                pet_info = data.get('petInfo', {})
                profile_info = data.get('profileInfo', {})
                social_info = data.get('socialInfo', {})
                
                nickname = basic_info.get('nickname', 'Not found')
                region = basic_info.get('region', 'Not found')
                level = basic_info.get('level', 'Not found')
                exp = basic_info.get('exp', '?')
                liked = basic_info.get('liked', 'Not found')
                honor_score = credit_score_info.get('creditScore', 'Not found')
                signature = social_info.get('signature', 'None')
                release_version = basic_info.get('releaseVersion', '?')
                badge_count = basic_info.get('badgeCnt', 'Not found')
                br_rank_points = basic_info.get('rankingPoints', '?')
                cs_rank_points = basic_info.get('csRankingPoints', '?')
                created_at = basic_info.get('createAt', 'Not found')
                last_login = basic_info.get('lastLoginAt', 'Not found')
                avatar_id = profile_info.get('avatarId', 'Not found')
                banner_id = basic_info.get('bannerId', 'Not found')
                account_type = basic_info.get('accountType', '?')
                title = basic_info.get('title', 'Not found')
                max_rank = basic_info.get('maxRank', '?')
                current_rank = basic_info.get('rank', '?')
                pet_name = pet_info.get('id', 'Not Found')
                pet_exp = pet_info.get('exp', 'Not Found')
                pet_level = pet_info.get('level', 'Not Found')
                pet_equipped = pet_info.get('isSelected', False)
                equipped_skills = profile_info.get('equipedSkills', 'Not found')
                clothes = profile_info.get('clothes', [])
                skin_color = profile_info.get('skinColor', 'Not found')
                is_selected_awaken = profile_info.get('isSelectedAwaken', False)
                gender = social_info.get('gender', 'Not found')
                language = social_info.get('language', 'Not found')
                rank_show = social_info.get('rankShow', 'Not found')
                time_active = social_info.get('timeActive', 'Not found')
                clan_name = clan_info.get('clanName', 'Not found')
                clan_id = clan_info.get('clanId', 'Not found')
                clan_level = clan_info.get('clanLevel', 'Not found')
                clan_members = clan_info.get('memberNum', 'Not found')
                clan_capacity = clan_info.get('capacity', '?')
                clan_captain_id = clan_info.get('captainId', 'Not found')
                diamond_cost = data.get('diamondCostRes', {}).get('diamondCost', '?')
                responding_region = 'Unknown'
                pet_skin_id = pet_info.get('skinId', 'Not Found')
                pet_skill_id = pet_info.get('selectedSkillId', 'Not Found')

            # Create embed
            embed = discord.Embed(
                title=f"📊 Player Information - {nickname}",
                color=discord.Color.blurple(),
                timestamp=datetime.now()
            )
            
            # Add player UID and region info
            embed.add_field(
                name="📋 Basic Information",
                value=f"**UID:** `{uid}`\n"
                      f"**Name:** {nickname}\n"
                      f"**Region:** {region}\n"
                      f"**API Region:** {responding_region}\n"
                      f"**Account Type:** {account_type}\n"
                      f"**Title:** {title}",
                inline=True
            )
            
            # Add stats section
            embed.add_field(
                name="📈 Player Stats",
                value=f"**Level:** {level}\n"
                      f"**Experience:** {exp}\n"
                      f"**Likes:** {liked}\n"
                      f"**Honor Score:** {honor_score}\n"
                      f"**Badges:** {badge_count}",
                inline=True
            )
            
            # Add rank information
            embed.add_field(
                name="🏆 Rank Information",
                value=f"**Current BR Rank:** {current_rank}\n"
                      f"**Max BR Rank:** {max_rank}\n"
                      f"**BR Points:** {br_rank_points}\n"
                      f"**CS Rank:** {basic_info.get('csRank', '?')}\n"
                      f"**CS Points:** {cs_rank_points}",
                inline=False
            )
            
            # Add activity information
            embed.add_field(
                name="🕒 Activity",
                value=f"**Created:** {self.convert_unix_timestamp(created_at)}\n"
                      f"**Last Login:** {self.convert_unix_timestamp(last_login)}\n"
                      f"**Version:** {release_version}\n"
                      f"**Season:** {basic_info.get('seasonId', '?')}",
                inline=True
            )
            
            # Add equipment and profile information
            equipment_text = f"**Avatar ID:** {avatar_id}\n"
            equipment_text += f"**Banner ID:** {banner_id}\n"
            equipment_text += f"**Skin Color:** {skin_color}\n"
            equipment_text += f"**Awaken:** {'Yes' if is_selected_awaken else 'No'}\n"
            equipment_text += f"**Clothes:** {len(clothes)} items"
            
            embed.add_field(
                name="🎮 Equipment",
                value=equipment_text,
                inline=True
            )
            
            # Add social information
            social_text = f"**Gender:** {gender.replace('Gender_', '')}\n"
            social_text += f"**Language:** {language.replace('Language_', '')}\n"
            social_text += f"**Rank Display:** {rank_show.replace('RankShow_', '')}\n"
            social_text += f"**Active Time:** {time_active.replace('TimeActive_', '')}\n"
            social_text += f"**Signature:** {signature[:50]}..."
            
            embed.add_field(
                name="👥 Social",
                value=social_text,
                inline=True
            )
            
            # Add pet information
            pet_text = f"**Equipped:** {'Yes' if pet_equipped else 'No'}\n"
            pet_text += f"**Pet ID:** {pet_name}\n"
            pet_text += f"**Level:** {pet_level}\n"
            pet_text += f"**Experience:** {pet_exp}\n"
            pet_text += f"**Skin ID:** {pet_skin_id}\n"
            pet_text += f"**Skill ID:** {pet_skill_id}"
            
            embed.add_field(
                name="🐾 Pet",
                value=pet_text,
                inline=True
            )
            
            # Add clan information
            if clan_name != 'Not found':
                clan_text = f"**Name:** {clan_name}\n"
                clan_text += f"**ID:** `{clan_id}`\n"
                clan_text += f"**Level:** {clan_level}\n"
                clan_text += f"**Members:** {clan_members}/{clan_capacity}\n"
                clan_text += f"**Captain ID:** `{clan_captain_id}`"
                
                embed.add_field(
                    name="🏰 Clan/Guild",
                    value=clan_text,
                    inline=True
                )
            
            # Add diamond cost
            embed.add_field(
                name="💎 Diamond Cost",
                value=f"**Cost:** {diamond_cost} diamonds",
                inline=True
            )
            
            # Add equipped skills
            if isinstance(equipped_skills, list):
                skills_text = f"**Skills Count:** {len(equipped_skills)}\n"
                if len(equipped_skills) > 0:
                    skills_text += f"**First Skill:** {equipped_skills[0]}\n"
                if len(equipped_skills) > 1:
                    skills_text += f"**Last Skill:** {equipped_skills[-1]}"
            else:
                skills_text = "No skills data"
            
            embed.add_field(
                name="⚔️ Equipped Skills",
                value=skills_text,
                inline=True
            )
            
            # Add weapon skins
            weapon_skins = basic_info.get('weaponSkinShows', [])
            if weapon_skins:
                weapons_text = f"**Weapons:** {len(weapon_skins)}\n"
                weapons_text += f"**First:** {weapon_skins[0]}\n"
                if len(weapon_skins) > 1:
                    weapons_text += f"**Last:** {weapon_skins[-1]}"
            else:
                weapons_text = "No weapon skins"
            
            embed.add_field(
                name="🔫 Weapon Skins",
                value=weapons_text,
                inline=True
            )

            embed.set_footer(text=f"DEVELOPED BY LINUX • Requested by {ctx.author.display_name}")
            
            await ctx.send(embed=embed)

            # Generate and send profile image if available
            if uid:
                try:
                    image_url = f"{self.generate_url}?uid={uid}"
                    print(f"Image URL = {image_url}")
                    if image_url:
                        async with self.session.get(image_url) as img_file:
                            if img_file.status == 200:
                                with io.BytesIO(await img_file.read()) as buf:
                                    file = discord.File(buf, filename=f"outfit_{uuid.uuid4().hex[:8]}.png")
                                    await ctx.send(file=file)
                                    print("Image sent successfully")
                            else:
                                print(f"HTTP Error: {img_file.status}")
                except Exception as e:
                    print("Image generation failed:", e)

        except Exception as e:
            await ctx.send(f" Unexpected error: `{e}`")
        finally:
            gc.collect()

    @commands.hybrid_command(name="check", description="Check Free Fire account info using API v1")
    @app_commands.describe(uid="FREE FIRE UID to check")
    async def check_api_v1(self, ctx: commands.Context, uid: str):
        """Command to use the new API endpoint you provided"""
        guild_id = str(ctx.guild.id)

        if not uid.isdigit() or len(uid) < 6:
            return await ctx.reply(" Invalid UID! It must:\n- Be only numbers\n- Have at least 6 digits", mention_author=False)

        if not await self.is_channel_allowed(ctx):
            return await ctx.send(" This command is not allowed in this channel.", ephemeral=True)

        cooldown = self.config_data["global_settings"]["default_cooldown"]
        if guild_id in self.config_data["servers"]:
            cooldown = self.config_data["servers"][guild_id]["config"].get("cooldown", cooldown)

        if ctx.author.id in self.cooldowns:
            last_used = self.cooldowns[ctx.author.id]
            if (datetime.now() - last_used).seconds < cooldown:
                remaining = cooldown - (datetime.now() - last_used).seconds
                return await ctx.send(f" Please wait {remaining}s before using this command again", ephemeral=True)

        self.cooldowns[ctx.author.id] = datetime.now()

        try:
            async with ctx.typing():
                async with self.session.get(f"https://api-info-v1.vercel.app/check?uid={uid}") as response:
                    if response.status == 404:
                        return await ctx.send(f" Player with UID `{uid}` not found.")
                    if response.status != 200:
                        return await ctx.send("API error. Try again later.")
                    
                    data = await response.json()
                    
                    # Create embed based on API response
                    embed = discord.Embed(
                        title="Player Check Result - API v1",
                        color=discord.Color.green(),
                        timestamp=datetime.now()
                    )
                    
                    # Check for new API format
                    if 'formatted_response' in data or 'raw_api_response' in data:
                        formatted_response = data.get('formatted_response', {})
                        raw_api_response = data.get('raw_api_response', {})
                        responding_region = data.get('responding_region', 'Unknown')
                        
                        # Add formatted response info
                        embed.add_field(
                            name="📋 Formatted Response",
                            value=f"**Nickname:** {formatted_response.get('nickname', 'N/A')}\n"
                                  f"**Region:** {formatted_response.get('region', 'N/A')}",
                            inline=True
                        )
                        
                        # Add API region info
                        embed.add_field(
                            name="🌍 API Region",
                            value=f"**Responding Region:** {responding_region}",
                            inline=True
                        )
                        
                        # Add raw response summary
                        if 'basicInfo' in raw_api_response:
                            basic_info = raw_api_response['basicInfo']
                            embed.add_field(
                                name="👤 Basic Info",
                                value=f"**Level:** {basic_info.get('level', 'N/A')}\n"
                                      f"**Exp:** {basic_info.get('exp', 'N/A')}\n"
                                      f"**Likes:** {basic_info.get('liked', 'N/A')}",
                                inline=True
                            )
                        
                        if 'clanBasicInfo' in raw_api_response:
                            clan_info = raw_api_response['clanBasicInfo']
                            embed.add_field(
                                name="🏰 Clan Info",
                                value=f"**Name:** {clan_info.get('clanName', 'N/A')}\n"
                                      f"**Level:** {clan_info.get('clanLevel', 'N/A')}\n"
                                      f"**Members:** {clan_info.get('memberNum', 'N/A')}",
                                inline=True
                            )
                        
                        # Show raw data count
                        embed.add_field(
                            name="📊 Data Summary",
                            value=f"**Fields in Response:** {len(data)}\n"
                                  f"**Raw API Fields:** {len(raw_api_response)}\n"
                                  f"**Formatted Fields:** {len(formatted_response)}",
                            inline=True
                        )
                        
                    else:
                        # Handle old structure
                        embed.add_field(
                            name="📋 Response Structure",
                            value="Old API structure detected",
                            inline=False
                        )
                        
                        # Add some basic fields if available
                        for key, value in data.items():
                            if isinstance(value, dict):
                                # Count nested items
                                embed.add_field(
                                    name=f"📁 {key}",
                                    value=f"{len(value)} items",
                                    inline=True
                                )
                            elif isinstance(value, list):
                                # Count list items
                                embed.add_field(
                                    name=f"📋 {key}",
                                    value=f"{len(value)} items",
                                    inline=True
                                )
                            elif key in ['nickname', 'region', 'level']:
                                # Show important fields
                                embed.add_field(
                                    name=f"📝 {key}",
                                    value=str(value)[:50],
                                    inline=True
                                )
                    
                    embed.set_footer(text="API v1 Check | DEVELOPED BY LINUX")
                    await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f" Unexpected error: `{e}`")
        finally:
            gc.collect()

    async def cog_unload(self):
        await self.session.close()

    async def _send_player_not_found(self, ctx, uid):
        embed = discord.Embed(
            title="❌ Player Not Found",
            description=(
                f"UID `{uid}` not found or inaccessible.\n\n"
                "⚠️ **Note:** IND servers are currently not working."
            ),
            color=0xE74C3C
        )
        embed.add_field(
            name="Tip",
            value="- Make sure the UID is correct\n- Try a different UID",
            inline=False
        )
        await ctx.send(embed=embed, ephemeral=True)

    async def _send_api_error(self, ctx):
        await ctx.send(embed=discord.Embed(
            title="⚠️ API Error",
            description="The Free Fire API is not responding. Try again later.",
            color=0xF39C12
        ))



async def setup(bot):
    await bot.add_cog(InfoCommands(bot))