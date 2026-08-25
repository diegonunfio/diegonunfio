# Setup

This template recreates the dark terminal-card aesthetic without GitSkins.

## 1. Create your profile repository

Create a public repository named exactly like your GitHub username.

Example:

    username/username

## 2. Copy these files into it

Keep the folders:

    assets/
    scripts/
    .github/workflows/

## 3. Edit profile.json

At minimum change:

- username
- name
- role
- tagline
- bio
- skills
- projects
- links

## 4. Push to GitHub

The workflow will:

- regenerate the SVG cards
- pull your real GitHub contribution calendar
- embed your GitHub avatar in the hero card
- generate the Space Shooter GIF
- update the generated files automatically

You can also run the workflow manually from:

Actions -> Update profile visuals -> Run workflow

## Local preview

Without a GitHub token:

    python scripts/generate_profile.py --offline

With a token:

    GITHUB_TOKEN=... python scripts/generate_profile.py

## Notes

GitHub profile READMEs do not allow arbitrary CSS or JavaScript, so the visual design is rendered as SVG files. This is why the template can closely mimic the GitSkins terminal cards while remaining free and self-hosted.
