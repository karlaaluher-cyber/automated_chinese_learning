import os
from io import StringIO

import pandas as pd
import google.genai as genai
import time
import smtplib
import markdown

from google.genai import types
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from dotenv import load_dotenv

load_dotenv()


client_key = os.getenv("client_key")
client = genai.Client(api_key = client_key)
sender_email = os.getenv("sender_email")
receiver_email = os.getenv("receiver_email")
password = os.getenv("password")

smtp_server = "smtp.gmail.com"
port = 587

def format_email(response_text):
# Split greeting+phrases from table
    table_start = int(response_text.find("|"))
    greeting_and_phrases = response_text[:table_start].strip()
    new_vocab = response_text[table_start:]
    
    # Convert table to HTML
    table_html = markdown.markdown(new_vocab, extensions=["tables"])
    
    # Build full HTML email
    html = f"""
    <html>
    <head>
    <style>
        body {{
            font-family: Georgia, serif;
            background-color: #f7f3ed;
            color: #1a1520;
            padding: 32px;
            max-width: 600px;
            margin: auto;
        }}
        .greeting {{
            font-size: 16px;
            margin-bottom: 24px;
            color: #4a2d5e;
            font-style: italic;
        }}
        .phrases {{
            font-size: 18px;
            line-height: 2;
            margin-bottom: 32px;
            padding: 20px;
            background: white;
            border-left: 3px solid #c9a84c;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        th {{
            background-color: #4a2d5e;
            color: #f7f3ed;
            padding: 10px 14px;
            text-align: left;
            letter-spacing: 1px;
            font-weight: normal;
        }}
        td {{
            padding: 10px 14px;
            border-bottom: 1px solid #e8e2da;
        }}
        tr:nth-child(even) td {{
            background-color: #f0ebe3;
        }}
    </style>
    </head>
    <body>
        <div class="greeting">{greeting_and_phrases.split(chr(10))[0]}</div>
        <div class="phrases">{'<br>'.join(greeting_and_phrases.split(chr(10))[1:])}</div>
        {table_html}
    </body>
    </html>
    """
    return html

def hsk_mailer():
    #Load the HSK list
    df = pd.read_csv("hsk_words.csv")
    #Add the personal interaction column acording to my current level (HSK 2 working on HSK 3)
    if "personal_interaction" not in df.columns:
        df.loc[df["level"]<=2,"personal_interaction"] = 8
        df.loc[df["level"]==3,"personal_interaction"] = 4
        df.loc[df["level"]>=4,"personal_interaction"] = 0
    #Save We'll check if this is necessary
    df.to_csv("hsk_words.csv", index=False)
    df = pd.read_csv("hsk_words.csv")
    #Prepare information for the AI prompt
    df_genai = df[["level","hanzi","pinyin_tone","english","personal_interaction"]]
    known = df_genai[df_genai["personal_interaction"] >= 5][["hanzi","pinyin_tone","english"]].to_csv(index=False)
    familiar = df_genai[df_genai["personal_interaction"].between(1,4)][["hanzi","pinyin_tone","english"]].to_csv(index=False)
    new = df_genai[df_genai["personal_interaction"] == 0][["hanzi","pinyin_tone","english"]].to_csv(index=False)
    #Prepare prompt
    prompt = f"""Act as a Chinese professor with ample experience with comprehensible input and a gift for storytelling. Your tone is funny but professional.

    Your student is a 26-year-old woman who started learning Chinese because she loves novels like Mo Dao Zu Shi, Tian Guan Ci Fu, and Yu Wu, and dramas/donghuas like Love Game in Eastern Fantasy and Link Click. She is strongly at HSK 2 and working her way into HSK 3.

    KNOWN WORDS (use ~65%):
    {known}

    FAMILIAR WORDS (use ~25%):
    {familiar}

    NEW WORDS (use ~10%):
    {new}

    Your goal is to write exactly 5 sentences in Mandarin Chinese (simplified characters) that together approximate this ratio across all five sentences combined: The 5 sentences together should use approximately:
    - 26 known words (65%)
    - 10 familiar words (25%)
    - 4 new words (10%)
    Total: ~40 words across all 5 sentences.
    The ratio is approximate and applies to the full set of five sentences, not to each sentence individually. The sentences must reference the world of xianxia cultivation novels — characters, situations, or themes from that genre — not generic topics about studying Chinese or life goals.

    Formatting rules you must follow exactly. Any violation of these rules is an error:
    - New words (from the NEW WORDS list) must be followed immediately by their pinyin in parentheses, like this: 渡劫(dù jié). No other words get pinyin.
    - Known words (from the KNOWN WORDS list) must appear with no pinyin and no annotation of any kind. No bold, no brackets, no parentheses.
    - Familiar words (from the FAMILIAR WORDS list) must appear with no pinyin and no annotation of any kind. No bold, no brackets, no parentheses.
    - The greeting to the student MUST be in ENGLISH.

    Here is an example of correct formatting:
    他在那座山上修炼了很多年，终于渡劫(dù jié)成功，成为了一位真正的仙人。
    In this example, 渡劫 is a new word and gets pinyin in parentheses. All other words are known or familiar and get no annotation of any kind.

    Your response must follow this exact structure and contain no text outside of it:
    1. A short greeting in English.
    2. The 5 sentences in Mandarin Chinese, following the formatting rules above.
    3. A table with columns: level, hanzi, pinyin_tone, english — containing ONLY new and familiar words that appear in the sentences. Do not include known words in the table."""
    #Attempt asking Gemini three times
    for attempt in range(3):
        try:
            response = client.models.generate_content(model="gemini-3.6-flash", contents=prompt)
            print(response.text)
            break
        except Exception as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(10)

    #Email
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = "HSK mailer - Your daily Chinese lesson is ready!"
    server = smtplib.SMTP(smtp_server, port)
    server.ehlo()
    server.starttls()
    server.login(sender_email, password)
    message = response.text.replace("**", "") #turn to text and delete ** 
    html_message = format_email(message)
    msg.attach(MIMEText(html_message, 'html', 'utf-8'))
    server.sendmail(sender_email, receiver_email,msg.as_string())
    server.quit()
    #Define new vocabulary used and save it as a hanzi list
    new_vocab = response.text[int(response.text.find("|")):]
    df_vocab = pd.read_csv(StringIO(new_vocab),sep="|")
    df_vocab = df_vocab.iloc[1:, 2].tolist() #Put it on list format
    used_vocab = [string.replace(" ","") for string in df_vocab] #erase empty spaces
    #Add one to personal interaction for the vocabulary seen on the text.
    df.loc[df["hanzi"].isin(used_vocab) & (df["personal_interaction"]<8),"personal_interaction"] += 1
    #Save changes in the csv file
    df.to_csv("hsk_words.csv",index=False)
    return print("Done")

if __name__ == "__main__":
    hsk_mailer()
