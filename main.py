import os
import discord
import interactions
import requests
import urllib.request
import time
from threading import Thread
from io import BytesIO
from db import Database
from dotenv import load_dotenv
from discord.ext import commands
from datetime import datetime

from PIL import Image

load_dotenv()

TOKEN = os.environ['TOKEN']
CHANNEL_ID = os.environ['CHANNEL_ID']
ENDRESULT_ID = os.environ['ENDRESULT_ID']

client = interactions.Client(TOKEN)

db1 = Database()
db2 = Database()
db3 = Database()

questions = ['Thanks for applying, what is your ingame name ?', 'Your forum username ?', 'Your pictures for the contest', 'Picture showing IGN']

buttonYes = interactions.Button(
    style=interactions.ButtonStyle.PRIMARY,
    label="Yes",
    custom_id="buttonYes"
)

buttonNo = interactions.Button(
    style=interactions.ButtonStyle.DANGER,
    label="No, i'm good",
    custom_id="buttonNo"
)

row = interactions.ActionRow(
    components=[buttonYes, buttonNo]
)

buttonYesDone = interactions.Button(
    style=interactions.ButtonStyle.PRIMARY,
    label="Yes",
    custom_id="buttonYesDone"
)

buttonNotDone = interactions.Button(
    style=interactions.ButtonStyle.DANGER,
    label="No",
    custom_id="buttonNotDone"
)

rowConfirmDone = interactions.ActionRow(
    components=[buttonYesDone, buttonNotDone]
)

def check_pending_timeout():
    db4 = Database()

    while True:
        rows = db4.query('SELECT author FROM user_pending WHERE date < Datetime("now", "-20 minutes");')

        if len(rows) > 0:
            for row in rows:
                author = str(row[0])
                db4.execute('DELETE FROM user_pending WHERE author = ?', author)
                db4.execute('DELETE FROM registrations WHERE author_id = ?', author)

        time.sleep(10)

def merge_images(images):

    merged_image = Image.new('RGBA', (2*images[0].size[0], 2*images[0].size[1]), (250,250,250,0))
    merged_image.paste(images[0], (0,0))
    
    if len(images) >= 2:
        merged_image.paste(images[1],(images[0].size[0], 0))

    if len(images) >= 3:
        merged_image.paste(images[2], (0, images[0].size[1]))
    
    if len(images) >= 4:
        merged_image.paste(images[3],(images[2].size[0], images[0].size[1]))

    image_binary = BytesIO()
    merged_image.save(image_binary, 'PNG')
    image_binary.seek(0)

    return image_binary
        
@client.component('buttonYesDone')
async def buttonYesDone_response(ctx):

    rows = db3.query('SELECT COUNT(*) FROM users_entries WHERE author_id = ?', str(ctx.user.id))
    if rows[0][0] > 0: return

    db3.execute('DELETE FROM user_pending WHERE author = ?', str(ctx.user.id))
    db3.execute('INSERT INTO users_entries(author_id, username) VALUES (?, ?)', str(ctx.user.id), str(ctx.user.username))
    await ctx.send('That\'s all, Thank you for your participation !')

    user_data = db1.query('SELECT pictures_contest FROM registrations WHERE author_id = ?', str(ctx.user.id))[0]

    image = interactions.EmbedImageStruct(url=user_data[0].split('\n')[0])
    embed = interactions.Embed(image=image, color=0x423862)

    res = await client._http.get_channel(ENDRESULT_ID)
    channel = interactions.Channel(**res, _client=ctx.client)

    await channel.send(embeds=embed)


@client.component('buttonNotDone')
async def buttonNo_response(ctx):

    rows = db3.query('SELECT COUNT(*) FROM users_entries WHERE author_id = ?', str(ctx.user.id))
    if rows[0][0] > 0: return

    db3.execute('DELETE FROM registrations WHERE author_id = ?', str(ctx.user.id)) 
    db3.execute('UPDATE user_pending SET question_id = 0')
    await ctx.send(questions[0])

@client.component('buttonYes')
async def buttonYes_response(ctx):
    
    rows = db3.query('SELECT question_id FROM user_pending WHERE author = ?', str(ctx.user.id))

    if len(rows) == 0: return
    if rows[0][0] != 2: return

    await ctx.send('Okay, please send more pictures')

@client.component('buttonNo')
async def buttonNo_response(ctx):
    rows = db3.query('SELECT question_id FROM user_pending WHERE author = ?', str(ctx.user.id))

    if len(rows) == 0: return
    if rows[0][0] != 2: return

    db3.execute('UPDATE user_pending SET question_id = ?', len(questions) - 1)
    await ctx.send('Okay, thanks for your pictures.\n\n' + questions[-1])


@client.event(name="on_message_create")
async def on_message(ctx):

    author = ctx.author

    if author.id == client.me.id: return
    
    # Check if it's a DM
    if not ctx.guild_id:

        rows = db3.query('SELECT question_id FROM user_pending WHERE author = ?', str(author.id))

        if len(rows) == 0: 
            channel = await ctx.get_channel()
            await channel.send('Please, do /apply in the server.\nNote: if you already did that, you got probably timeout after 20 minutes, so please retry')
            return

        msg = ctx.content

        user = rows[0]
        q = int(user[0])

        if q == 0:
            db2.execute('INSERT INTO registrations(author_id, ingame_name) VALUES(?, ?)', str(author.id), str(msg))            

        if q == 1:
            db2.execute('UPDATE registrations SET forum_name = ? WHERE author_id = ?', str(msg), str(author.id))

        if q == 2:
            
            error = False
            if ctx.attachments is not None:
                for pic in ctx.attachments:
                    if pic.filename.endswith('.jpg') or pic.filename.endswith('.png'):
                        error = False
                    else:
                        error = True

                if not error:
                    for pic in ctx.attachments:
                        db1.execute('UPDATE registrations SET pictures_contest = IFNULL(pictures_contest, "") || ? WHERE author_id = ?', str(pic.url) + '\n', str(author.id))
                        
                        # Check max 3 images
                        pic_contest = db1.query('SELECT pictures_contest FROM registrations WHERE author_id = ?', str(author.id))[0]
                        if len(pic_contest[0].split('\n')) > 3:
                            break

            elif msg.startswith("https://media.discordapp.net/") or msg.startswith('https://cdn.discordapp.com/'):
                pic_url = msg
                if pic_url.endswith('.jpg') or pic_url.endswith('.png'):
                    
                    r = requests.get(pic_url)
                    if r.status_code != 200:
                        await ctx.reply('Error while fetching you\'re image')
                        return

                    db1.execute('UPDATE registrations SET pictures_contest = IFNULL(pictures_contest, "") || ? WHERE author_id = ?', str(pic_url) + '\n', str(author.id))

                else:
                    error = True

            else:
                error = True


            if error:
                await ctx.reply('Error, please send one or multiple supported images (.jpg or .png)')
                return

            # Check max 3 images
            pic_contest = db1.query('SELECT pictures_contest FROM registrations WHERE author_id = ?', str(author.id))[0]

            if len(pic_contest[0].split('\n')) <= 3:
                await ctx.reply('Do you want to add more images ?', components=row)
                return

        if q == 3:
            error = False

            if ctx.attachments is not None:
                pic = ctx.attachments[0]
                if pic.filename.endswith('.jpg') or pic.filename.endswith('.png'):
                    db1.execute('UPDATE registrations SET pictures_ign = ? WHERE author_id = ?', str(pic.url) + '\n', str(author.id))
                else:
                    error = True

            elif msg.startswith("https://media.discordapp.net/") or msg.startswith('https://cdn.discordapp.com/'):
                pic_url = msg
                if pic_url.endswith('.jpg') or pic_url.endswith('.png'):
                    r = requests.get(pic_url)
                    if r.status_code != 200:
                        await ctx.reply('Error while fetching you\'re image')
                        return
                    
                    db1.execute('UPDATE registrations SET pictures_ign = ? WHERE author_id = ?', str(pic_url) + '\n', str(author.id))

                else:
                    error = True

            else:
                error = True

            if error:
                await ctx.reply('Error, please send one or multiple supported images (.jpg or .png)')
                return


            user_data = db1.query('SELECT ingame_name, forum_name, pictures_contest, pictures_ign FROM registrations WHERE author_id = ?', str(author.id))[0]


            # Merging multiple images in one image
            user_agent = 'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.0.7) Gecko/2009021910 Firefox/3.0.7'
            headers={'User-Agent':user_agent,} 
            
            images = []
            for url in user_data[2].split('\n'):
                
                if not url.startswith('https://'): continue

                request = urllib.request.Request(url,None,headers)
                with urllib.request.urlopen(request) as req:
                    f = BytesIO(req.read())
                
                images.append(Image.open(f).resize((426, 240)))
            
            # Picture IGN
            request = urllib.request.Request(user_data[3], None, headers)
            with urllib.request.urlopen(request) as req:
                f = BytesIO(req.read())
            
            images.append(Image.open(f).resize((426, 240)))

            image_binary = merge_images(images)

            file = interactions.File('image.png', fp=image_binary)
            image = interactions.EmbedImageStruct(url=f"attachment://image.png")

            embed = interactions.Embed(title='Correct ?', color=0x423862, image=image, fields=[interactions.EmbedField(name='Ingame name', value=user_data[0]),
                                                                                interactions.EmbedField(name='Forum name', value=user_data[1]),
                                                                                interactions.EmbedField(name='Your pictures', value="\u200b")])
            channel = await ctx.get_channel()
            await channel.send(files=file, embeds=embed, components=rowConfirmDone)

            image_binary.close()

            return

        # Update question id
        id_ = int(user[0]) + 1
        await ctx.reply(questions[id_])

        db1.execute('UPDATE user_pending SET question_id = ?', id_)

@client.event
async def on_ready():
    print('Logged in as', client.me.name)
    print('-----------')

    Thread(target=check_pending_timeout).start()

@client.command(name='apply', description='Apply for Elios')
async def apply(ctx: interactions.CommandContext):
    if ctx.channel_id == CHANNEL_ID:
        author = ctx.author
    
        rows = db2.query('SELECT COUNT(*) AS cnt FROM user_pending WHERE author = ?', str(author.id))

        if rows[0][0] > 0: return

        rows = db2.query('SELECT COUNT(*) AS cnt FROM users_entries WHERE author_id = ?', str(author.id))

        if rows[0][0] > 0: return

        db2.execute(f'INSERT INTO user_pending(author, question_id, date) VALUES(?, 0, strftime(\'%Y-%m-%d %H:%M:%S\', datetime(\'now\')))', str(author.id))

        await author.send(questions[0])
        await ctx.send('Apply Received !', ephemeral=True)


if __name__ == '__main__':
    try:
        client.start()
    except KeyboardInterrupt:
        exit(1)