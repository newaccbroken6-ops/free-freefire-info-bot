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
            
            # Handle different possible response structures
            # Based on the API response you shared, let's handle the actual structure
            if 'basicInfo' in data:
                # Traditional structure
                basic_info = data.get('basicInfo', {})
                captain_info = data.get('captainBasicInfo', {})
                clan_info = data.get('clanBasicInfo', {})
                credit_score_info = data.get('creditScoreInfo', {})
                pet_info = data.get('petInfo', {})
                profile_info = data.get('profileInfo', {})
                social_info = data.get('socialInfo', {})
            elif 'rawApiResponse' in data or 'formattedResponse' in data:
                # Structure with rawApiResponse and formattedResponse
                raw_response = data.get('rawApiResponse', data.get('basicInfo', {}))
                formatted_response = data.get('formattedResponse', data.get('basicInfo', {}))
                
                # Use formatted response as primary source, fallback to raw response
                basic_info = {**raw_response, **formatted_response}  # Merge both, formatted takes precedence
                captain_info = {}
                clan_info = {}
                credit_score_info = {}
                pet_info = {}
                profile_info = {}
                social_info = {}
            else:
                # Direct structure - try to identify and extract the actual data
                basic_info = {}
                captain_info = {}
                clan_info = {}
                credit_score_info = {}
                pet_info = {}
                profile_info = {}
                social_info = {}
                
                # Look for known fields in the top level response
                for key, value in data.items():
                    if isinstance(value, dict):
                        # Check if this nested object contains player info
                        if any(player_key in value for player_key in ['accountId', 'nickname', 'level']):
                            if 'accountId' in value:
                                basic_info = value
                                break
                    elif key in ['nickname', 'accountId', 'region', 'level', 'exp', 'liked']:
                        basic_info[key] = value
                
                # If we couldn't find basic info in nested objects, use the top level
                if not basic_info and isinstance(data, dict):
                    basic_info = data
            
            # Extract all possible values with extensive fallbacks based on the API response structure
            nickname = basic_info.get('nickname', basic_info.get('name', basic_info.get('playerName', data.get('nickname', data.get('name', 'Not found')))))
            region = basic_info.get('region', basic_info.get('Region', data.get('region', data.get('Region', 'Not found'))))
            level = basic_info.get('level', basic_info.get('playerLevel', basic_info.get('AccountLevel', data.get('level', data.get('playerLevel', 'Not found')))))
            exp = basic_info.get('exp', basic_info.get('experience', basic_info.get('Exp', data.get('exp', data.get('experience', '?')))))
            liked = basic_info.get('liked', basic_info.get('likes', basic_info.get('Likes', data.get('liked', data.get('likes', 'Not found')))))
            honor_score = credit_score_info.get('creditScore', basic_info.get('honorScore', basic_info.get('CreditScore', data.get('creditScore', data.get('honorScore', 'Not found')))))
            signature = social_info.get('signature', basic_info.get('signature', basic_info.get('Signature', data.get('signature', 'None') or 'None')))
            release_version = basic_info.get('releaseVersion', basic_info.get('latestOB', basic_info.get('ReleaseVersion', data.get('releaseVersion', data.get('latestOB', '?')))))
            badge_count = basic_info.get('badgeCnt', basic_info.get('badges', basic_info.get('BadgeCount', data.get('badgeCnt', data.get('badges', 'Not found')))))
            br_rank_points = basic_info.get('rankingPoints', basic_info.get('brRank', basic_info.get('BrRankPoints', data.get('rankingPoints', data.get('brRank', '?')))))
            cs_rank_points = basic_info.get('csRankingPoints', basic_info.get('csRank', basic_info.get('CsRankPoints', data.get('csRankingPoints', data.get('csRank', '?')))))
            created_at = basic_info.get('createAt', basic_info.get('createdAt', basic_info.get('CreateAt', data.get('createAt', data.get('createdAt', 'Not found')))))
            last_login = basic_info.get('lastLoginAt', basic_info.get('lastLoginTime', basic_info.get('LastLoginAt', data.get('lastLoginAt', data.get('lastLoginTime', 'Not found')))))
            avatar_id = profile_info.get('avatarId', basic_info.get('avatarId', basic_info.get('AvatarId', data.get('avatarId', data.get('AvatarId', 'Not found')))))
            banner_id = basic_info.get('bannerId', basic_info.get('BannerId', data.get('bannerId', data.get('BannerId', 'Not found'))))
            pin_id_raw = captain_info.get('pinId', basic_info.get('pinId', basic_info.get('PinId', data.get('pinId', data.get('PinId', 'Default')))))
            pin_id = pin_id_raw if captain_info else 'Default'
            equipped_skills = profile_info.get('equipedSkills', basic_info.get('equippedSkills', basic_info.get('EquippedSkills', data.get('equipedSkills', data.get('equippedSkills', 'Not found')))))
            pet_equipped_nested = data.get('petEquipped', False)
            pet_equipped = pet_info.get('isSelected', basic_info.get('petEquipped', basic_info.get('PetEquipped', data.get('isSelected', pet_equipped_nested))))
            pet_name_raw = pet_info.get('name', basic_info.get('petName', basic_info.get('PetName', data.get('name', data.get('petName', 'Not Found')))))
            pet_name = pet_name_raw if pet_info else 'Not Found'
            pet_exp = pet_info.get('exp', basic_info.get('petExp', basic_info.get('PetExp', data.get('exp', data.get('petExp', 'Not Found')))))
            pet_level = pet_info.get('level', basic_info.get('petLevel', basic_info.get('PetLevel', data.get('level', data.get('petLevel', 'Not Found')))))

            embed = discord.Embed(
                title=" Player Information",
                color=discord.Color.blurple(),
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=ctx.author.display_avatar.url)

            # Create basic info section with extensive fallbacks
            basic_info_fields = [
                "**┌  ACCOUNT BASIC INFO**",
                f"**├─ Name**: {nickname}",
                f"**├─ UID**: `{uid}`",
                f"**├─ Level**: {level} (Exp: {exp})",
                f"**├─ Region**: {region}",
                f"**├─ Likes**: {liked}",
                f"**├─ Honor Score**: {honor_score}",
                f"**└─ Signature**: {signature}"
            ]
            embed.add_field(name="", value="\n".join(basic_info_fields), inline=False)
          


            # Create activity section with extensive fallbacks
            activity_fields = [
                "**┌  ACCOUNT ACTIVITY**",
                f"**├─ Most Recent OB**: {release_version}",
                f"**├─ Current BP Badges**: {badge_count}",
                f"**├─ BR Rank**: {'' if basic_info.get('showBrRank', True) else 'Not found'} {br_rank_points} ",
                f"**├─ CS Rank**: {'' if basic_info.get('showCsRank', True) else 'Not found'} {cs_rank_points} ",
                f"**├─ Created At**: {self.convert_unix_timestamp(created_at)}",
                f"**└─ Last Login**: {self.convert_unix_timestamp(last_login)}"

            ]
            embed.add_field(name="", value="\n".join(activity_fields), inline=False)

            # Create overview section with extensive fallbacks
            overview_fields = [
                "**┌  ACCOUNT OVERVIEW**",
                f"**├─ Avatar ID**: {avatar_id}",
                f"**├─ Banner ID**: {banner_id}",
                f"**├─ Pin ID**: {pin_id}",
                f"**└─ Equipped Skills**: {equipped_skills}"
            ]
            embed.add_field(name="", value="\n".join(overview_fields), inline=False)

            # Create pet details section with extensive fallbacks
            pet_fields = [
                "**┌  PET DETAILS**",
                f"**├─ Equipped?**: {'Yes' if pet_equipped else 'Not Found'}",
                f"**├─ Pet Name**: {pet_name}",
                f"**├─ Pet Exp**: {pet_exp}",
                f"**└─ Pet Level**: {pet_level}"
            ]
            embed.add_field(name="", value="\n".join(pet_fields), inline=False)
            
            # Add any additional fields from the API response that weren't covered above
            all_api_keys = set()
            for d in [data, basic_info, captain_info, clan_info, credit_score_info, pet_info, profile_info, social_info]:
                if isinstance(d, dict):
                    all_api_keys.update(d.keys())
                        
            # Define keys that are already displayed
            displayed_keys = {
                'nickname', 'name', 'playerName', 'uid', 'level', 'playerLevel', 'exp', 'experience',
                'region', 'Region', 'liked', 'likes', 'creditScore', 'honorScore', 'signature',
                'releaseVersion', 'latestOB', 'badgeCnt', 'badges', 'rankingPoints', 'brRank',
                'csRank', 'showBrRank', 'showCsRank', 'createAt', 'createdAt', 'lastLoginAt',
                'lastLoginTime', 'avatarId', 'bannerId', 'pinId', 'equipedSkills', 'equippedSkills',
                'isSelected', 'petEquipped', 'petName', 'petExp', 'petLevel', 'clanName', 'clanId',
                'id', 'clanLevel', 'level', 'memberNum', 'members', 'capacity', 'maxMembers',
                'accountId', 'title', 'exp', 'badgeCnt', 'badges', 'showBrRank', 'showCsRank',
                'rankingPoints', 'brRank', 'csRankingPoints', 'csRank', 'basicInfo', 'captainBasicInfo',
                'clanBasicInfo', 'creditScoreInfo', 'petInfo', 'profileInfo', 'socialInfo',
                'captainInfo', 'clanInfo'
            }
                        
            # Find additional keys not already displayed
            additional_keys = all_api_keys - displayed_keys
                        
            if additional_keys:
                additional_fields = ["**┌  ADDITIONAL DATA**"]
                for key in sorted(additional_keys):
                    if key not in ['basicInfo', 'captainBasicInfo', 'clanBasicInfo', 'creditScoreInfo', 'petInfo', 'profileInfo', 'socialInfo']:
                        value = data.get(key, 'N/A')
                        # Convert timestamp if needed
                        if 'at' in key.lower() and str(value).isdigit():
                            value = self.convert_unix_timestamp(value)
                        # Ensure value is a string and limit its length
                        value_str = str(value)[:100]  # Limit individual value length
                        field_name = str(key).replace('At', ' Time').replace('_', ' ').title()
                        # Ensure the entire field string doesn't exceed limits
                        field_str = f"**├─ {field_name}**: {value_str}"
                        if len(field_str) > 1024:
                            field_str = field_str[:1020] + "..."
                        additional_fields.append(field_str)
                additional_fields.append("**└─**")
                embed.add_field(name="", value="\n".join(additional_fields), inline=False)
            
            # Handle clan info
            final_clan_info = clan_info if clan_info else (data.get('clanInfo', {}) if 'clanInfo' in data else data.get('clan', {}))
            final_captain_info = captain_info if captain_info else (data.get('captainInfo', {}) if 'captainInfo' in data else data.get('captain', {}))
                        
            if final_clan_info:
                guild_info = [
                    "**┌  GUILD INFO**",
                    f"**├─ Guild Name**: {final_clan_info.get('clanName', final_clan_info.get('name', 'Not found'))}",
                    f"**├─ Guild ID**: `{final_clan_info.get('clanId', final_clan_info.get('id', 'Not found'))}`",
                    f"**├─ Guild Level**: {final_clan_info.get('clanLevel', final_clan_info.get('level', 'Not found'))}",
                    f"**├─ Live Members**: {final_clan_info.get('memberNum', final_clan_info.get('members', 'Not found'))}/{final_clan_info.get('capacity', final_clan_info.get('maxMembers', '?'))}"
                ]
                if final_captain_info:
                    guild_info.extend([
                        "**└─ Leader Info**:",
                        f"    **├─ Leader Name**: {final_captain_info.get('nickname', final_captain_info.get('name', 'Not found'))}",
                        f"    **├─ Leader UID**: `{final_captain_info.get('accountId', final_captain_info.get('id', 'Not found'))}`",
                        f"    **├─ Leader Level**: {final_captain_info.get('level', final_captain_info.get('level', 'Not found'))} (Exp: {final_captain_info.get('exp', final_captain_info.get('experience', '?'))})",
                        f"    **├─ Last Login**: {self.convert_unix_timestamp(final_captain_info.get('lastLoginAt', final_captain_info.get('lastLoginTime', 'Not found')))}",
                        f"    **├─ Title**: {final_captain_info.get('title', final_captain_info.get('title', 'Not found'))}",
                        f"    **├─ BP Badges**: {final_captain_info.get('badgeCnt', final_captain_info.get('badges', '?'))}",
                        f"    **├─ BR Rank**: {'' if final_captain_info.get('showBrRank', True) else 'Not found'} {final_captain_info.get('rankingPoints', final_captain_info.get('brRank', 'Not found'))}",
                        f"    **└─ CS Rank**: {'' if final_captain_info.get('showCsRank', True) else 'Not found'} {final_captain_info.get('csRankingPoints', final_captain_info.get('csRank', 'Not found'))} "
                    ])
                embed.add_field(name="", value="\n".join(guild_info), inline=False)



            embed.set_footer(text="DEVELOPED BY LINUX")
            await ctx.send(embed=embed)

            if region and uid:
                try:
                    image_url = f"{self.generate_url}?uid={uid}"
                    print(f"Url d'image = {image_url}")
                    if image_url:
                        async with self.session.get(image_url) as img_file:
                            if img_file.status == 200:
                                with io.BytesIO(await img_file.read()) as buf:
                                    file = discord.File(buf, filename=f"outfit_{uuid.uuid4().hex[:8]}.png")
                                    await ctx.send(file=file)  # ✅ ENVOYER L'IMAGE
                                    print("Image envoyée avec succès")
                            else:
                                print(f"Erreur HTTP: {img_file.status}")
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
                # Use the new API endpoint you provided
                async with self.session.get(f"https://api-info-v1.vercel.app/check?uid={uid}") as response:
                    if response.status == 404:
                        return await ctx.send(f" Player with UID `{uid}` not found.")
                    if response.status != 200:
                        return await ctx.send("API error. Try again later.")
                    
                    data = await response.json()
                    
                    # Create embed based on API response
                    embed = discord.Embed(
                        title="Player Check Result",
                        color=discord.Color.green(),
                        timestamp=datetime.now()
                    )
                    
                    # Process the API response and create appropriate embed fields
                    if isinstance(data, dict):
                        # Handle special nested structures like rawApiResponse and formattedResponse
                        if 'rawApiResponse' in data or 'formattedResponse' in data:
                            # Flatten these nested structures
                            for key, value in data.items():
                                if isinstance(value, dict):
                                    # Add nested fields with prefixes
                                    for nested_key, nested_value in value.items():
                                        field_name = f"{key.replace('Response', '')}.{nested_key}".replace('Api.', 'API ').replace('formatted.', 'Formatted ').title()
                                        field_value = str(nested_value) if nested_value is not None else "N/A"
                                        
                                        # Handle timestamp conversions
                                        if 'at' in nested_key.lower() and str(nested_value).isdigit():
                                            field_value = self.convert_unix_timestamp(nested_value)
                                        
                                        # Limit field name length and value length for Discord embed limits
                                        field_name = field_name[:256]  # Max field name length
                                        field_value = field_value[:1024]  # Max field value length
                                        
                                        # Ensure the total field string doesn't exceed limits
                                        total_field_length = len(field_name) + len(field_value)
                                        if total_field_length > 1024:
                                            # Reduce the value length to fit within limits
                                            available_space = 1024 - len(field_name) - 10  # Leave some space for formatting
                                            if available_space > 0:
                                                field_value = field_value[:available_space] + "..."
                                        
                                        embed.add_field(name=field_name, value=field_value, inline=False)
                                else:
                                    # Handle direct fields
                                    field_name = str(key).replace('At', ' Time').replace('_', ' ').title()
                                    field_value = str(value) if value is not None else "N/A"
                                    
                                    # Handle timestamp conversions
                                    if 'at' in key.lower() and str(value).isdigit():
                                        field_value = self.convert_unix_timestamp(value)
                                    
                                    # Limit field name length and value length for Discord embed limits
                                    field_name = field_name[:256]  # Max field name length
                                    field_value = field_value[:1024]  # Max field value length
                                    
                                    # Ensure the total field string doesn't exceed limits
                                    total_field_length = len(field_name) + len(field_value)
                                    if total_field_length > 1024:
                                        # Reduce the value length to fit within limits
                                        available_space = 1024 - len(field_name) - 10  # Leave some space for formatting
                                        if available_space > 0:
                                            field_value = field_value[:available_space] + "..."
                                    
                                    embed.add_field(name=field_name, value=field_value, inline=False)
                        else:
                            # Process normal dictionary structure
                            for key, value in data.items():
                                # Handle timestamp conversions
                                if 'at' in key.lower() and value and str(value).isdigit():
                                    # This is likely a timestamp field
                                    converted_time = self.convert_unix_timestamp(int(value))
                                    field_name = str(key).replace('At', ' Time').replace('_', ' ').title()
                                    field_value = converted_time
                                else:
                                    # Regular field
                                    field_name = str(key).replace('At', ' Time').replace('_', ' ').title()
                                    field_value = str(value) if value is not None else "N/A"
                                
                                # Limit field name length and value length for Discord embed limits
                                field_name = field_name[:256]  # Max field name length
                                field_value = field_value[:1024]  # Max field value length
                                
                                # Ensure the total field string doesn't exceed limits
                                total_field_length = len(field_name) + len(field_value)
                                if total_field_length > 1024:
                                    # Reduce the value length to fit within limits
                                    available_space = 1024 - len(field_name) - 10  # Leave some space for formatting
                                    if available_space > 0:
                                        field_value = field_value[:available_space] + "..."
                                
                                embed.add_field(name=field_name, value=field_value, inline=False)
                    else:
                        embed.add_field(name="Response", value=str(data)[:1024], inline=False)
                    
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
