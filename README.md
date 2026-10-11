# NYC Indie Shows Calendar

A private-source repository that publishes a subscribable calendar of the current New York City indie-show listings on Oh My Rockness.

The feed refreshes every six hours, preserves New York local times, links every event to its original Oh My Rockness listing, uses stable event IDs, deduplicates listings, and marks removed events as cancelled after two successful refreshes.

The Netlify deployment publishes no landing page. The calendar and status file are available only at the private, unguessable feed path stored in this private repository. Search indexing and caching are disabled through `netlify.toml`.
