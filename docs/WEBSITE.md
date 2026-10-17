# Project website maintenance

Public URL: https://jimmy-xuzimo.github.io/deepseek-local-bridge/.

The site is served directly from `main:/docs` using the repository's existing GitHub Pages configuration. There is no package install or frontend build step. Existing Markdown documentation and the `#top`, `#features`, `#how`, `#clients` and `#download` anchors remain available.

## Local preview

From the repository root:

```sh
python -m http.server 8080 --directory docs
```

Open http://localhost:8080. Clipboard controls require HTTPS or localhost. Push changes to `main` to trigger the existing Pages deployment.

## Files

- `index.html`: structure, initial Chinese text, download links and metadata. The Chinese HTML is the source of the Chinese dictionary and keeps essential content available without JavaScript.
- `assets/preferences.js`: applies the saved or system theme before CSS loads. Reuses the previous website's `dsb-theme` and `dsb-lang` keys so existing preferences survive.
- `assets/site.js`: English dictionary, language/theme controls, tabs, copying, request generation and flow illustration.
- `assets/site.css`: both themes, layout tokens, responsive styles and reduced-motion behavior.
- `assets/favicon.svg` and `assets/social.png`: website mark and 1200×630 sharing cover.

Theme selection cycles **System → Dark → Light → System**. First visits follow the OS theme and browser language. Preferences are stored locally. Both languages share one URL; this is not separate Chinese and English indexing. Search/social crawlers generally see the initial Chinese HTML and static metadata.

## Content rules

The bridge runs locally, but sends messages and attachments to DeepSeek's web service. Do not describe it as offline inference or claim all data stays on-device. The project is unofficial and subject to web changes, account controls and service terms.

Codex CLI uses Responses and requires CC Switch routing to convert to Chat Completions. Tool calling is prompt-based, buffers the complete answer, and can fall back to text. One account handles requests serially. Preserve these distinctions when updating copy.

The flow illustration is browser-only and does not contact localhost or real accounts. It runs only after a click, finishes after three timed steps, and resets if hidden or scrolled out of view while running. Reduced-motion mode immediately shows the final state. Request toggles only generate Bash text; requests are never executed by the site, and no real API key is stored or requested.

The six download links are pinned to the verified **v0.1.1** release. When upgrading, verify the actual published asset names, update all six links, the release label and checksum URL together, and check the latest-release destination. Portable builds still require a usable browser environment. Do not equate CI packaging with real-account verification on every platform.

## Verification

Check mobile (including narrow widths and landscape), tablets in both orientations, desktop and large screens. Test both languages, both themes, system changes, saved preferences, client and source tabs, clipboard feedback, request toggles, the flow illustration, keyboard navigation and reduced motion. All three client panels should fit every viewport.

Verify the repository subpath, existing documentation URLs, canonical/social URLs and published release assets. No external fonts, analytics, CDN scripts or runtime API calls are used. Automated accessibility checks supplement, rather than replace, physical-device and assistive-technology testing.
