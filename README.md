# Claude Skills Collection

This repository contains a curated collection of skills for use with Claude Desktop app and Claude Code CLI. Skills extend Claude's capabilities with specialized knowledge, workflows, and domain-specific expertise.

## Repository Structure

Each skill in this repository is organized with two subdirectories to support both Claude platforms:

```
skill-name/
 desktop/          # Skill files for Claude Desktop app (API-based)
    SKILL.md
    ...
 code/            # Skill files for Claude Code CLI (file-based)
     SKILL.md
     ...
```

- **`desktop/`** - Contains the version of the skill optimized for Claude Desktop app, which uses the Claude API for skill management
- **`code/`** - Contains the version of the skill optimized for Claude Code CLI, which uses local filesystem-based skill discovery

Skills may differ between platforms due to their different capabilities and use cases.

## Installation Instructions

### Installing Skills in Claude Code CLI

Claude Code uses a file-based approach where skills are automatically discovered from your filesystem.

#### Personal Skills (Available Across All Projects)

1. **Create the skill directory:**
   ```bash
   mkdir -p ~/.claude/skills/skill-name
   ```

2. **Copy the skill files:**
   ```bash
   cp -r skill-name/code/* ~/.claude/skills/skill-name/
   ```

3. **Verify installation:**
   Skills are automatically discovered. You can verify by asking Claude: "What skills are available?"

#### Project Skills (Shared with Your Team)

1. **Create the skill directory in your project:**
   ```bash
   mkdir -p .claude/skills/skill-name
   ```

2. **Copy the skill files:**
   ```bash
   cp -r skill-name/code/* .claude/skills/skill-name/
   ```

3. **Commit and share:**
   ```bash
   git add .claude/skills/
   git commit -m "Add skill-name skill"
   git push
   ```

Team members will automatically have access to the skill when they pull the repository.

#### File Paths Reference

| Skill Type | Location |
|-----------|----------|
| Personal Skills | `~/.claude/skills/{skill-name}/SKILL.md` |
| Project Skills | `./.claude/skills/{skill-name}/SKILL.md` |

### Installing Skills in Claude Desktop App

Claude Desktop allows you to import skills by creating and uploading a zip file.

#### Step 1: Create a Zip File

Navigate to the skill's desktop directory and create a zip file containing all skill files:

```bash
cd skill-name/desktop
zip -r ../skill-name.zip .
cd ../..
```

Or, if you prefer to zip from the parent directory:

```bash
cd skill-name
zip -r skill-name.zip desktop/*
cd ..
```

**Important:** The zip file should contain the skill files (like `SKILL.md`) at the root level or in the expected directory structure.

#### Step 2: Import into Claude Desktop

1. Open the Claude Desktop app
2. Navigate to Settings > Skills
3. Click "Import Skill" or "Add Skill"
4. Select the zip file you created (e.g., `skill-name.zip`)
5. The skill will be imported and available for use in your conversations

Once imported, the skill will appear in your skills list and can be activated in conversations where needed.

## Skill Structure

Each skill requires a `SKILL.md` file with the following format:

```markdown
---
name: skill-name
description: Brief description of what this skill does and when to use it
---

# Skill Name

## Instructions
Provide clear, step-by-step guidance for Claude.

## Examples
Show concrete examples of using this skill.
```

### Required Fields

- **`name`**: Lowercase letters, numbers, and hyphens only (max 64 characters)
- **`description`**: Max 1024 characters. Should include both what the skill does AND when to use it

### Optional Fields

- **`allowed-tools`**: (Claude Code only) Restrict which tools Claude can use with this skill

## Platform Differences

| Feature | Claude Code CLI | Claude Desktop (API) |
|---------|----------------|---------------------|
| Storage | Local filesystem | Anthropic servers |
| Discovery | Automatic | Manual via API |
| Sharing | Via git | Via skill IDs |
| Max Skills | Unlimited | 8 per request |
| Versioning | Manual | Automatic |

## Available Skills

Browse the directories in this repository to explore available skills. Each skill directory contains:
- Platform-specific implementations (`desktop/` and `code/`)
- Documentation on what the skill does
- Examples of when to use it

## Contributing

When adding a new skill to this repository:

1. Create a new directory with a descriptive name (lowercase, hyphens only)
2. Add `desktop/` and `code/` subdirectories
3. Include a `SKILL.md` file in each subdirectory
4. Ensure the skill description clearly states what it does and when to use it
5. Test the skill on both platforms before committing

## Resources

- [Claude Code Skills Documentation](https://code.claude.com/docs/en/skills.md)
- [Claude API Skills Guide](https://platform.claude.com/docs/en/build-with-claude/skills-guide.md)
- [Claude Code CLI Documentation](https://code.claude.com/docs)

## License

[Add your license information here]
