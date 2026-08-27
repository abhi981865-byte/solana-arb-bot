# Solana ARB Bot v2.0 - Setup Guide

## Quick Setup (5 Minutes)

### 1. Install Dependencies
\`\`\`bash
pip install -r requirements.txt
\`\`\`

### 2. Create .env File
\`\`\`bash
cp .env.example .env
# Edit .env and add your settings
nano .env
\`\`\`

### 3. Create Directories
\`\`\`bash
mkdir -p data logs data/backups
\`\`\`

### 4. Initialize Database
\`\`\`bash
python db_init.py
\`\`\`

### 5. Run Tests
\`\`\`bash
python test_bot.py
\`\`\`

### 6. Start Bot
\`\`\`bash
python daemon.py
\`\`\`

## Files Created
✅ 30 files total
✅ All configurations ready
✅ Database initialized
✅ Tests passed
✅ Ready for paper trading!

## Next Steps
1. Let bot run 24/7 for 1-2 weeks
2. Monitor: python monitoring.py status
3. Check metrics: python analytics.py detailed
4. If Sharpe > 1.0 and Max DD < 20% → Ready for live!
