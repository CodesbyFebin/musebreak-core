# Publishing documentation and checking discovery

## Current observed state

On October 30, 2026 the repository was public, GitHub Wiki was enabled, Pages was disabled, and description/homepage/topics were empty. These are observations, not proof that a separate wiki or site was published. The connected GitHub code tool cannot administer Pages or repository metadata. This change prepares the source, validation and deploy workflow; it does not claim an administrative setting changed.

## Build and preview

```sh
python -m pip install -r docs/requirements.txt
python scripts/check_docs.py
python scripts/build_docs.py
python -m http.server 8080 --directory _site
```

The generated site contains only selected public documentation and crawler text. It never copies the database, .env, private keys, live receipts or the whole repository. No JavaScript is needed to read it. The canonical deployment target is https://codesbyfebin.github.io/musebreak-core/; local preview paths are mounted at / for convenience, while canonicals remain the production target.

## GitHub Pages deployment

1. Review and merge the documentation PR. It is independent of PR #1 and does not merge the invoice application code. The published site explicitly describes that implementation as pending; no application deployment is implied.
2. In repository **Settings → Pages**, select **GitHub Actions** as the publishing source. This needs repository maintainer/admin access, which the code connector does not provide.
3. The Pages workflow builds on main pushes; from the default branch you can also run it with Actions → Public documentation → Run workflow.
4. Confirm the deployment succeeds and open the reported live URL. Check status 200, canonical URLs, sitemap, links and text files before announcing availability.

Only the default branch can deploy. Pull requests run build/link validation without Pages write permission or production deployment. This avoids publishing unmerged feature claims as releases. The workflow uses GitHub's official Pages actions with separate build/deploy permissions.

## Wiki sources

The source-controlled pages under docs/wiki are rendered into Pages. A separate GitHub Wiki is another git repository; this change does not push to it. Maintainers can copy the source pages there if desired, adjusting relative links. The source-controlled site remains the canonical documentation workflow so changes receive ordinary review.

## Repository metadata to set

Description: **Experimental self-hosted AI gateway and Business OS: exact-payload invoice approvals, signed receipts, and independent local-state verification.**

Homepage after a successful deployment: **https://codesbyfebin.github.io/musebreak-core/**

Suggested accurate topics: **ai-agents, business-software, self-hosted, fastapi, sqlite, ed25519, audit-trail, invoice, webllm, human-in-the-loop**. Topics describe code; they are not proof of event participation or ranking.

## Robots and AI text

Project Pages is hosted below /musebreak-core/. Crawlers consult robots.txt at the host root, so the project-local copy cannot set the host's policy. The sitemap and ordinary HTML links are still useful discovery aids. agents.txt is descriptive, AGENTS.md is for contributors, and llms.txt is an optional retrieval convention, not mandatory search markup. No indexing or LLM-awareness guarantee is possible.

## Measurement and references

Record successful deployments and broken-link checks first. With separately authorized Search Console access, inspect indexing and real queries; compare equivalent periods rather than claiming a score from file presence. No search analytics account is connected by this change. No fake testimonials, hidden keyword text or mass generated landing pages are added.

Primary references: [GitHub Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages), [publishing source](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site), [Google generative search guidance](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide), [Search Essentials](https://developers.google.com/search/docs/essentials).

Return to [wiki home](Home.md).
