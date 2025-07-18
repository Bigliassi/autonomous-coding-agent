# 🐙 GitHub Repository Setup

## Step 1: Create GitHub Repository

1. **Go to GitHub**: https://github.com/new
2. **Repository Settings**:
   - Repository name: `autonomous-coding-agent`
   - Description: `AI-powered autonomous coding agent with continuous task processing`
   - Visibility: `Public` (or Private if preferred)
   - ✅ Add a README file: **UNCHECK THIS** (we already have one)
   - ✅ Add .gitignore: **UNCHECK THIS** (we already have one)
   - ✅ Choose a license: Optional

3. **Click "Create repository"**

## Step 2: Connect Your Local Repository

After creating the repository on GitHub, run these commands in your project directory:

```bash
# Add GitHub as remote origin
git remote add origin https://github.com/YOUR_USERNAME/autonomous-coding-agent.git

# Push your existing commits
git push -u origin master

# Verify the connection
git remote -v
```

**Replace `YOUR_USERNAME` with your actual GitHub username!**

## Step 3: Configure GitHub Integration in the Agent

### Option A: Via Web Dashboard (Recommended)
1. Start the agent: `python main.py`
2. Open http://127.0.0.1:5000/settings
3. In the "GitHub Integration" section:
   - Enter your GitHub username
   - Enter your Personal Access Token (see below)
   - Enter repository name: `autonomous-coding-agent`
4. Click "Setup GitHub Remote"

### Option B: Via Environment Variables
1. Create `.env` file from `env_template.txt`
2. Add your GitHub credentials:
```env
GITHUB_USERNAME=your_actual_username
GITHUB_TOKEN=your_personal_access_token
```

## Step 4: Create GitHub Personal Access Token

**Why needed?** The agent needs permission to push commits automatically.

1. **Go to GitHub Settings**: https://github.com/settings/tokens
2. **Click "Generate new token (classic)"**
3. **Token Settings**:
   - Note: `Autonomous Coding Agent`
   - Expiration: `90 days` (or longer)
   - **Required Scopes**:
     - ✅ `repo` (Full control of private repositories)
     - ✅ `workflow` (Update GitHub Action workflows)
4. **Click "Generate token"**
5. **Copy the token** (you won't see it again!)

## Step 5: Test the Integration

```bash
# Test git operations
git status
git add .
git commit -m "Test commit from autonomous agent"
git push

# Test the agent CLI
python cli.py --status
python cli.py "Create a test function"
```

## Step 6: Enable Auto-Push

In your `.env` file or via the web dashboard:
```env
GIT_AUTO_PUSH=True
```

Now every successful task will be automatically committed and pushed to your GitHub repository!

## Troubleshooting

### Authentication Failed
- Double-check your Personal Access Token
- Ensure token has `repo` scope
- Try regenerating the token

### Push Rejected
```bash
# If you have conflicts, pull first
git pull origin master --rebase
git push origin master
```

### Repository Not Found
- Verify repository name matches exactly
- Check if repository is public/private and token has access
- Ensure username is correct

## Security Notes

- ⚠️ Never commit `.env` files with real tokens
- 🔒 Use tokens with minimal required permissions
- ⏰ Set token expiration dates
- 🔄 Rotate tokens regularly

## What Happens Next

Once configured, the autonomous agent will:
1. 🔄 Process tasks from the queue
2. 🧪 Generate and test code
3. ✅ Commit successful results
4. 📤 Push to your GitHub repository
5. 📊 Track everything in the dashboard

Every task becomes a traceable commit in your repository history! 