# NYC Indie Shows Calendar

A private-source repository that publishes a subscribable calendar of the current New York City indie-show listings on Oh My Rockness.

The feed refreshes every six hours, follows every page of the current Oh My Rockness schedule, preserves New York local times, links every event to its original listing, uses stable event IDs, deduplicates listings, and marks removed events as cancelled after two successful refreshes.

The Netlify deployment includes a plain subscription landing page in the same style as the other calendar projects. The calendar and status file use a private, unguessable feed path stored in this private repository. Search indexing and caching are disabled through `netlify.toml`.
