(function runner(xpg, debug = false) {
  function getViaPath(obj, ...pathItems) {
    let cur = obj[pathItems.shift()];
    if (cur == null) return null;
    while (pathItems.length) {
      cur = cur[pathItems.shift()];
      if (cur == null) return null;
    }
    return cur;
  }

  function delay(delayTime = 3000) {
    return new Promise(resolve => {
      setTimeout(resolve, delayTime);
    });
  }
  function waitForPredicate(predicate) {
    return new Promise(resolve => {
      const cb = () => {
        if (predicate()) {
          resolve();
        } else {
          window.requestAnimationFrame(cb);
        }
      };
      window.requestAnimationFrame(cb);
    });
  }
  async function waitForAndSelectElement(fromNode, selector) {
    let elem = fromNode.querySelector(selector);
    if (!elem) {
      await waitForPredicate(() => fromNode.querySelector(selector) != null);
      elem = fromNode.querySelector(selector);
    }
    return elem;
  }

  let reactProps = {
    rootContainer: '_reactRootContainer',
    internalRoot: '_internalRoot',
    onDomNode: '__reactInternalInstance',
    rootHostElemId: 'react-root',
    mProps: 'memoizedProps'
  };
  function getReactRootHostElem(alternativeId) {
    const id =
      alternativeId != null ? alternativeId : reactProps.rootHostElemId;
    return document.getElementById(id);
  }
  function getInternalRootOnElem(elem) {
    return elem[reactProps.internalRoot];
  }
  function reactInstanceFromDOMElem(elem) {
    const keys = Object.keys(elem);
    let i = 0;
    let len = keys.length;
    let internalKey;
    for (; i < len; ++i) {
      if (keys[i].startsWith(reactProps.onDomNode)) {
        internalKey = keys[i];
        break;
      }
    }
    if (!internalKey) throw new Error('Could not find react internal key');
    return elem[internalKey];
  }
  function reactInstancesFromElements(elems, selectingFn) {
    const renderedNodes = [];
    const length = elems.length;
    let i = 0;
    let node;
    let reactInstance;
    for (; i < length; ++i) {
      node = elems[i];
      reactInstance = reactInstanceFromDOMElem(node);
      if (selectingFn(reactInstance.key)) {
        renderedNodes.push({ node, reactInstance });
      }
    }
    return renderedNodes;
  }
  function findChildWithKey(reactInstance, key) {
    let child = reactInstance.child;
    while (child) {
      if (child.key && child.key === key) {
        return child;
      }
      child = child.child;
    }
    return undefined;
  }

  function scrollIntoView(elem) {
    if (elem == null) return;
    elem.scrollIntoView({
      behavior: 'auto',
      block: 'center',
      inline: 'center'
    });
  }
  function scrollIntoViewWithDelay(elem, delayTime = 1000) {
    scrollIntoView(elem);
    return delay(delayTime);
  }

  function click(elem) {
    let clicked = false;
    if (elem != null) {
      elem.dispatchEvent(
        new MouseEvent('mouseover', {
          view: window,
          bubbles: true,
          cancelable: true
        })
      );
      elem.click();
      clicked = true;
    }
    return clicked;
  }
  async function clickWithDelay(elem, delayTime = 1000) {
    let clicked = click(elem);
    if (clicked) {
      await delay(delayTime);
    }
    return clicked;
  }
  function selectElemFromAndClickWithDelay(
    selectFrom,
    selector,
    delayTime = 1000
  ) {
    return clickWithDelay(selectFrom.querySelector(selector), delayTime);
  }
  async function selectFromAndClickNTimesWithDelay(
    selectFrom,
    selector,
    n,
    delayTime = 1000
  ) {
    let i = 0;
    let clickMe;
    for (; i < n; ++i) {
      clickMe = selectFrom.querySelector(selector);
      if (clickMe) {
        await clickWithDelay(clickMe, delayTime);
      }
    }
  }

  function maybePolyfillXPG(cliXPG) {
    if (
      typeof cliXPG !== 'function' ||
      cliXPG.toString().indexOf('[Command Line API]') === -1
    ) {
      return function(xpathQuery, startElem) {
        if (startElem == null) {
          startElem = document;
        }
        const snapShot = document.evaluate(
          xpathQuery,
          startElem,
          null,
          XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,
          null
        );
        const elements = [];
        let i = 0;
        let len = snapShot.snapshotLength;
        while (i < len) {
          elements.push(snapShot.snapshotItem(i));
          i += 1;
        }
        return elements;
      };
    }
    return cliXPG;
  }
  function addBehaviorStyle(styleDef) {
    if (document.getElementById('$wrStyle$') == null) {
      const style = document.createElement('style');
      style.id = '$wrStyle$';
      style.textContent = styleDef;
      document.head.appendChild(style);
    }
  }

  addBehaviorStyle('.wr-debug-visited {border: 6px solid #3232F1;}');
  class InstagramPosts {
    constructor(xpg) {
      this.xpg = xpg;
      this.reactProps = {
        multiImages: 'sidecarChildren'
      };
      this.reactRoot = getReactRootHostElem();
      this.internalRoot = getInternalRootOnElem(this.reactRoot);
      this.profilePage = window._sharedData.entry_data.ProfilePage[0];
      this.userId = this.profilePage.graphql.user.id;
      this.userName = this.profilePage.graphql.user.username;
      this.componentKeys = {
        profileKey: `userprofile_${this.userName}`,
        postGrid: 'virtual_posts_grid'
      };
      this.selectors = {
        multipleImages: 'span.coreSpriteSidecarIconLarge',
        hasVideo: 'span.coreSpriteVideoIconLarge',
        postTopMostContainer: 'article',
        rightChevron: 'button > div.coreSpriteRightChevron',
        postPopupArticle: `${new Array(3)
          .fill(0)
          .map(() => 'div[role="dialog"]')
          .join(' > ')} > article`,
        multiImageDisplayDiv: 'div > div[role="button"]'
      };
      this.xpathQ = {
        postPopupClose: '//body/div/div/button[contains(text(), "Close")]',
        loadMoreComments: '//li/button[contains(text(), "Load more comments")]',
        showAllComments: '//li/button[contains(text(), "View all")]'
      };
      this.rootProfileNode = null;
      this.store = null;
      this.articleInternals = null;
      this.postGrid = null;
      this.postScrollContainer = null;
      this.postWrappingDiv = null;
      this.rowClassName = '';
      this.posts = null;
      this.postsByUserId = null;
      this._unsubscribe = null;
      this.seenPostRows = new Set();
      this._didInit = false;
      this.keyedComponentSelector = this.keyedComponentSelector.bind(this);
    }
    init() {
      if (this._didInit) return;
      this._getReduxStore();
      this._getPostLoaderInternals();
      this._didInit = true;
    }
    getRenderedPostRows() {
      return reactInstancesFromElements(
        this.postWrappingDiv.stateNode.childNodes,
        this.keyedComponentSelector
      );
    }
    keyedComponentSelector(key) {
      const select = !this.seenPostRows.has(key);
      if (select) {
        this.seenPostRows.add(key);
      }
      return select;
    }
    async *postIterator() {
      let currentPostRows = this.getRenderedPostRows();
      do {
        yield* this.consumeRow(currentPostRows);
        currentPostRows = this.getRenderedPostRows();
      } while (this.loadedCount < this.totalCount);
      if (currentPostRows.length === 0) {
        currentPostRows = this.getRenderedPostRows();
      }
      do {
        yield* this.consumeRow(currentPostRows);
        currentPostRows = this.getRenderedPostRows();
      } while (currentPostRows.length > 0);
    }
    async *consumeRow(postRow) {
      let row, j, numPosts, post, posts;
      let i = 0,
        numRows = postRow.length;
      for (; i < numRows; ++i) {
        row = postRow[i];
        if (debug) {
          row.node.classList.add('wr-debug-visited');
        }
        await scrollIntoViewWithDelay(row.node);
        posts = row.node.childNodes;
        numPosts = posts.length;
        for (j = 0; j < numPosts; ++j) {
          post = posts[j];
          await this.scrollIntoView(post);
          if (this.isMultiImagePost(post)) {
            await this.handleMultiImagePost(post);
          } else if (this.isVideoPost(post)) {
            await this.handleVideoPost(post);
          } else {
            await this.handleCommentsOnly(post);
          }
          yield post;
        }
      }
    }
    async handleMultiImagePost(post) {
      const { portal, displayDiv } = await this.openPost(post);
      const displayDivReact = reactInstanceFromDOMElem(displayDiv);
      const numImages =
        getViaPath(
          displayDivReact,
          'child',
          reactProps.mProps,
          this.reactProps.multiImages,
          'length'
        ) || 100;
      await selectFromAndClickNTimesWithDelay(
        portal,
        this.selectors.rightChevron,
        numImages
      );
      await this.loadAllComments();
      await this.closePost();
    }
    async handleVideoPost(post) {
      const { displayDiv } = await this.openPost(post);
      await selectElemFromAndClickWithDelay(displayDiv, 'a[role="button"]');
      await this.loadAllComments();
      await this.closePost();
    }
    async handleCommentsOnly(post) {
      await this.openPost(post);
      await this.loadAllComments();
      await this.closePost();
    }
    async loadAllComments() {
      let moreComments = this.getMoreComments();
      while (moreComments.length) {
        await clickWithDelay(moreComments[0], 1500);
        moreComments = this.getMoreComments();
      }
    }
    async openPost(post) {
      await clickWithDelay(post.childNodes[0]);
      const portal = await waitForAndSelectElement(
        document,
        this.selectors.postPopupArticle
      );
      const displayDiv = portal.querySelector(
        this.selectors.multiImageDisplayDiv
      );
      return { portal, displayDiv };
    }
    async closePost() {
      const close = this.xpg(this.xpathQ.postPopupClose)[0];
      if (close) {
        await clickWithDelay(close);
      }
    }
    getMoreComments() {
      const moreComments = this.xpg(this.xpathQ.loadMoreComments);
      if (moreComments.length === 0)
        return this.xpg(this.xpathQ.showAllComments);
      return moreComments;
    }
    isMultiImagePost(post) {
      return post.querySelector(this.selectors.multipleImages) != null;
    }
    isVideoPost(post) {
      return post.querySelector(this.selectors.hasVideo) != null;
    }
    get hasNextPage() {
      return this.postsByUserId.get(this.userId).pagination.hasNextPage;
    }
    get isFetching() {
      return this.postsByUserId.get(this.userId).pagination.isFetching;
    }
    get totalCount() {
      return this.postsByUserId.get(this.userId).count;
    }
    get loadedCount() {
      return this.postsByUserId.get(this.userId).pagination.loadedCount;
    }
    [Symbol.asyncIterator]() {
      return this.postIterator();
    }
    _getReduxStore() {
      let rootProfileNode = findChildWithKey(
        this.internalRoot.current,
        this.componentKeys.profileKey
      );
      if (!rootProfileNode) throw new Error('could not find root profile node');
      this.rootProfileNode = rootProfileNode;
      this.store = this.rootProfileNode.stateNode.context.store;
      let currentState = this.store.getState();
      this.posts = currentState.posts;
      this.postsByUserId = currentState.profilePosts.byUserId;
      this._unsubscribe = this.store.subscribe(this._storeListener.bind(this));
    }
    _storeListener() {
      let nextState = this.store.getState();
      if (this.postsByUserId !== nextState.profilePosts.byUserId) {
        this.posts = nextState.posts;
        this.postsByUserId = nextState.profilePosts.byUserId;
        console.log(
          `isFetching=${this.isFetching}, hasNextPage=${
            this.hasNextPage
          }, loadedCount=${this.loadedCount}`
        );
      }
    }
    _getPostLoaderInternals() {
      const articleInternals = reactInstanceFromDOMElem(
        document.querySelector(this.selectors.postTopMostContainer)
      );
      let postGrid;
      let postScrollContainer;
      let postWrappingDiv;
      let child = articleInternals.child;
      let rowClassName;
      let nextChild;
      while (child) {
        if (child.key === this.componentKeys.postGrid) postGrid = child;
        if (child.type === 'div') {
          postScrollContainer = child;
          nextChild = child.child;
          if (nextChild && nextChild.sibling) {
            postWrappingDiv = nextChild.sibling;
          }
          break;
        }
        if (child.memoizedProps && child.memoizedProps.rowClassName) {
          rowClassName = child.memoizedProps.rowClassName;
        }
        child = child.child;
      }
      this.articleInternals = articleInternals;
      this.postGrid = postGrid;
      this.postScrollContainer = postScrollContainer;
      this.postWrappingDiv = postWrappingDiv;
      this.rowClassName = rowClassName;
    }
  }
  const instaPosts = new InstagramPosts(maybePolyfillXPG(xpg));
  instaPosts.init();
  window.$WRTLIterator$ = instaPosts.postIterator();
  window.$WRIteratorHandler$ = async function() {
    const next = await $WRTLIterator$.next();
    return next.done;
  };
})($x);
