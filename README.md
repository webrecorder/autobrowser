## `bootstrap.sh`
- builds the wr-behaviors api image (tag webrecorder/behaviors-api:latest)
- builds the autobrowser driver image (tag webrecorder/autobrowser:latest)


## `scripts/docker.sh`
0 args 
- builds the wr-behaviors api image (tag webrecorder/behaviors-api:latest)
- builds the autobrowser driver image (tag webrecorder/autobrowser:latest)

arg "buildBehaviorsAPIImage":
- builds the wr-behaviors api image (tag webrecorder/behaviors-api:latest)

arg "buildBehaviors":
- rebuilds the behavior portion of the webrecorder/behaviors-api:latest image

arg "driver":
- builds the autobrowser driver image (tag webrecorder/autobrowser:latest)

## autobrowser driver env keys
- BEHAVIOR_API_URL: The base URL used by behaviors api 
- FETCH_BEHAVIOR_ENDPOINT: The URL of the behaviors api endpoint for retrieving just the behaviors JavaScript
- FETCH_BEHAVIOR_INFO_ENDPOINT: The URL of the behaviors api endpoint for retrieving just the behaviors info
- CRAWL_NO_NETCACHE: Should the browsers network cache be disable (any value, test is existance)
- NAV_TO: How long should the timeout for navigation to become fully completed by (number)
- BEHAVIOR_RUN_TIME: How long should the behaviors be allowed to run for (number)
- NUM_TABS: How many tabs should the be created per browser connected to (number)
- TAB_TYPE: Which tab type should be used (BehaviorTab or CrawlerTab)
- REDIS_URL: The URL to be used to connect to redis
- SHEPARD_HOST: The URL that shepard is listening on
- WAIT_FOR_Q: Should the crawler tab wait for the frontier q to become populated (existence)
