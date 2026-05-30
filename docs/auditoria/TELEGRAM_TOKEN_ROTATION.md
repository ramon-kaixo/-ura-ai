# Telegram Token Rotation Guide

## Why Rotate the Token?

The previous Telegram token has been exposed in:
- Code commits
- Configuration files
- Documentation

For security reasons, you should rotate it immediately.

## Steps to Rotate Telegram Token

### 1. Create a New Bot in Telegram

1. Open Telegram and search for @BotFather
2. Send the command: `/newbot`
3. Follow the prompts:
   - Choose a name for your bot (e.g., "URA Assistant v2")
   - Choose a username (must end in `bot`, e.g., `ura_assistant_v2_bot`)
4. BotFather will give you a new token like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`

### 2. Update Environment Variables

Edit `.env` file:
```bash
TELEGRAM_TOKEN=your_new_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 3. Update Telegram Bridge Configuration

If you have a `telegram_config.json`, update it:
```json
{
  "token": "your_new_token_here",
  "chat_id": "your_chat_id_here"
}
```

### 4. Test the New Token

Test the new token with curl:
```bash
curl https://api.telegram.org/botYOUR_NEW_TOKEN/getMe
```

### 5. Delete the Old Bot (Optional but Recommended)

1. Open Telegram and search for @BotFather
2. Send the command: `/mybots`
3. Select the old bot
4. Click "Delete Bot"

## Security Best Practices

- Never commit `.env` file to git
- Add `.env` to `.gitignore`
- Use different tokens for development and production
- Rotate tokens periodically (every 3-6 months)
- Monitor bot activity for unauthorized usage

## Monitoring Token Usage

Check your bot's activity:
```bash
curl https://api.telegram.org/botYOUR_TOKEN/getUpdates
```

If you see unexpected activity, rotate the token immediately.
