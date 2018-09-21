var reactRoot = document.querySelector('#react-root')._reactRootContainer;
var internalRoot = reactRoot._internalRoot;
var profilePage = window._sharedData.entry_data.ProfilePage[0];
var userId = profilePage.graphql.user.id;
var userName = profilePage.graphql.user.username;
var profileKey = `userprofile_${userName}`;


var InstagramUserProfile = class {
  constructor() {
    this.reactRoot = document.querySelector('#react-root')._reactRootContainer;
    this.internalRoot = this.reactRoot._internalRoot;
    this.profilePage = window._sharedData.entry_data.ProfilePage[0];
    this.userId = this.profilePage.graphql.user.id;
    this.userName = this.profilePage.graphql.user.username;
    this.profileKey = `userprofile_${this.userName}`;
    this.rootProfileNode = this.findProfileRootNode();
    this.stateNode = this.rootProfileNode.stateNode;
    /**
     *
     * @type {({getState: function(): Object, subscribe: function(listener): function()})}
     */
    this.store = this.stateNode.context.store;

    this.currentByUserId = this.getPostsByUserIdFromStore();
    this.postFetchingListener = this.postFetchingListener.bind(this);

    this.unsubToStore = this.store.subscribe(this.postFetchingListener);
    this.postInfo = getPostInformation();
  }

  postFetchingListener() {
    let nextByUserId = this.getPostsByUserIdFromStore();
    if (nextByUserId && nextByUserId !== this.currentByUserId) {
      let info = nextByUserId.get(this.userId);
      let pagination = info.pagination;
      console.log(
        `isFetching=${pagination.isFetching}, hasNextPage=${
          pagination.hasNextPage
        }, loadedCount=${pagination.loadedCount}`
      );
      this.currentByUserId = nextByUserId;
    }
  }

  start () {
    this.postInfo.postLoader.querySelectorAll(this.postInfo.rowClassName)
  }

  /**
   * @return {boolean}
   */
  isFetching() {
    return this.currentByUserId.get(this.userId).pagination.isFetching;
  }

  /**
   * @return {number}
   */
  loadedCount() {
    return this.currentByUserId.get(this.userId).pagination.loadedCount;
  }

  /**
   * @return {boolean}
   */
  hasNextPage() {
    return this.currentByUserId.get(this.userId).pagination.hasNextPage;
  }

  /**
   *
   * @return {?Immutable.Map}
   */
  getPostsByUserIdFromStore() {
    let nextState = this.store.getState();
    if (!nextState) return;
    let profilePosts = nextState.profilePosts;
    if (!profilePosts) return;
    return profilePosts.byUserId;
  }

  findProfileRootNode() {
    let child = this.internalRoot.current.child;
    while (child) {
      if (child.key && child.key === this.profileKey) {
        return child;
      }
      child = child.child;
    }
    throw new Error('could not find root profile node');
  }
};

function findProfileRootNode(fiber) {
  let child = fiber.child;
  while (child) {
    if (child.key && child.key === profileKey) {
      return child;
    }
    child = child.child;
  }
  return null;
}


function getReactInternalInstance(elem) {
  const keys = Object.keys(elem);
  let i = 0;
  let len = keys.length;
  let internalKey;
  while (i < len) {
    if (keys[i].startsWith('__reactInternalInstance')) {
      internalKey = keys[i];
      break;
    }
    i += 1;
  }
  if (!internalKey) throw new Error('Could not find react internal key');
  return elem[internalKey];
}

/**
 *
 * @return {{postContainer: {elem: Element, react: *}, postLoader: {elem: Element, react: *}, rowClassName: string}}
 */
function getPostInformation() {
  const postContainer = document.querySelector('article');
  const postInternal = getReactInternalInstance(postContainer);
  if (postInternal.stateNode !== postContainer) {
    throw new Error(
      'The found post internal react node stateNode is not the same as the postContainers'
    );
  }
  let child = postInternal.child;
  let rowClassName;
  while (child) {
    if (child.memoizedProps.rowClassName) {
      rowClassName = child.memoizedProps.rowClassName;
      break;
    }
    child = child.child;
  }
  if (!rowClassName) throw new Error('Could not find the row class names');
  const postLoader = document.querySelector('article > div > div');
  const postLoaderRI = getReactInternalInstance(postLoader);
  return {
    postContainer: {
      elem: postContainer,
      react: postInternal
    },
    postLoader: {
      elem: postLoader,
      react: postLoaderRI
    },
    rowClassName
  };
}

var rootProfileNode = findProfileRootNode(internalRoot.current);
if (!rootProfileNode) {
  throw new Error('could not find root profile node');
}

var stateNode = rootProfileNode.stateNode;
/**
 *
 * @type {({getState: function(): Object, subscribe: function(listener): function()})}
 */
var store = stateNode.context.store;

// window.addEventListener('mousewheel', () => {
//   console.log(rootProfileNode.child.memoizedProps);
// });

var currentUnsubscribe;
function swapListener(newListener) {
  currentUnsubscribe();
  currentUnsubscribe = store.subscribe(newListener);
}

function getPostsByUserIdFromStore(store) {
  let nextState = store.getState();
  if (!nextState) return;
  let profilePosts = nextState.profilePosts;
  if (!profilePosts) return;
  return profilePosts.byUserId;
}

var curUserByIdState = getPostsByUserIdFromStore(store);
var initialInfo = curUserByIdState.get(userId);
var numPosts = initialInfo.count;
var loadedCount = initialInfo.pagination.loadedCount;

var listener = () => {
  let nextUserByIdState = getPostsByUserIdFromStore(store);
  if (nextUserByIdState && nextUserByIdState !== curUserByIdState) {
    let info = nextUserByIdState.get(userId);
    let pagination = info.pagination;
    console.log(
      `isFetching=${pagination.isFetching}, hasNextPage=${
        pagination.hasNextPage
      }, loadedCount=${pagination.loadedCount}`
    );
    curUserByIdState = nextUserByIdState;
  }
};


currentUnsubscribe = store.subscribe(listener);