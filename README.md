## `bootstrap.sh`
- ensures submodules are initialized
- builds the wr-behaviors image
- bundles the behaviors js
- builds the autobrowserpy image used by docker-compose.yml

## `scripts/submodules.sh`
ensures submodules are initialized

## `scripts/docker.sh`
0 args 
- builds the wr-behaviors image
- bundles the behaviors js
- builds the autobrowserpy image used by docker-compose.yml

arg "behaviorImage":
- builds the wr-behaviors image required to bundle the behaviors

arg "behaviors":
- bundles the behaviors and places in autobrowser/behaviors/behaviorjs

arg "py":
- builds the autobrowserpy image used by docker-compose.yml

