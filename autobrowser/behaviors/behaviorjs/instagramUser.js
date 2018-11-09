(function runner(xpg, debug) {
  /**
   * @desc Retrieves the property of an object, or item in array at index, based
   * on the supplied path.
   * @example
   *   const obj = { a: { b: { c: [1, 2, 3] } } }
   *   const two = getViaPath(obj, 'a', 'b', 'c', 1); // two == 2
   * @param {Object | Array | Element | Node} obj
   * @param {string | number} pathItems
   * @return {any}
   */
  function getViaPath(obj, ...pathItems) {
    let cur = obj[pathItems.shift()];
    if (cur == null) return null;
    while (pathItems.length) {
      cur = cur[pathItems.shift()];
      if (cur == null) return null;
    }
    return cur;
  }

  /**
   * @param {string} xpathQuery
   * @param {Element | Document} startElem
   * @return {XPathResult}
   */

  /**
   * @param {function(string, ?HTMLElement | ?Document)} cliXPG
   * @return {function(string, ): Array<HTMLElement>}
   */
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

  /**
   * @param {string} selector - the selector to be use
   * @param {Element|Node|HTMLElement|Document} [context] - element to use rather than document for the querySelector call
   * @returns {Element | Node | HTMLElement | HTMLIFrameElement}
   */
  function qs(selector, context) {
    if (context != null) return context.querySelector(selector);
    return document.querySelector(selector);
  }

  function addBehaviorStyle(styleDef) {
    if (document.getElementById('$wrStyle$') == null) {
      const style = document.createElement('style');
      style.id = '$wrStyle$';
      style.textContent = styleDef;
      document.head.appendChild(style);
    }
  }

  /**
   * @param {string} selector
   * @param {Document | Element} [cntx]
   * @return {boolean}
   */
  function selectorExists(selector, cntx) {
    return qs(selector, cntx) != null;
  }

  /**
   * @param {number} [delayTime = 3000]
   * @returns {Promise<void>}
   */
  function delay(delayTime = 3000) {
    return new Promise(resolve => {
      setTimeout(resolve, delayTime);
    });
  }

  /**
   * @desc Returns a promise that resolves when the supplied predicate function
   * returns a truthy value. Polling via setInterval 1sec.
   * @param {function(): boolean} predicate
   * @return {Promise<void>}
   */
  function waitForPredicate(predicate) {
    return new Promise(resolve => {
      let int = setInterval(() => {
        if (predicate()) {
          clearInterval(int);
          resolve();
        }
      }, 1000);
    });
  }

  /**
   * @desc Calls `fromNode.querySelector` using the supplied selector. If the
   * return value of the first calls is null/undefined then waits for the same call
   * to return a truthy value and then returns the element the selector matches.
   * @param {Element | Node | HTMLElement} fromNode
   * @param {string} selector
   * @return {Promise<Element | Node | HTMLElement>}
   */
  async function waitForAndSelectElement(fromNode, selector) {
    let elem = qs(selector, fromNode);
    if (!elem) {
      await waitForPredicate(() => selectorExists(selector));
      elem = qs(selector, fromNode);
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

  /**
   * @param {string} [alternativeId]
   * @return {HTMLElement}
   */
  function getReactRootHostElem(alternativeId) {
    const id =
      alternativeId != null ? alternativeId : reactProps.rootHostElemId;
    return document.getElementById(id);
  }

  /**
   * @param {HTMLElement | Element | Node} elem
   * @return {Object}
   */
  function getInternalRootOnElem(elem) {
    return elem[reactProps.internalRoot];
  }

  /**
   * @param {HTMLElement | Element | Node} elem
   * @return {Object}
   */
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

  /**
   * @param {Array<Node | HTMLElement | Element>} elems
   * @param {function(key: string): boolean} selectingFn
   * @return {Array<{node: HTMLElement | Element | Node, reactInstance: Object}>}
   */
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

  /**
   * @param {Object} reactInstance
   * @param {string} key
   * @return {?Object}
   */
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

  /**
   * @param {Element | HTMLElement | Node} elem - The element to be scrolled into view
   */
  function scrollIntoView(elem) {
    if (elem == null) return;
    elem.scrollIntoView({
      behavior: 'smooth',
      block: 'center',
      inline: 'center'
    });
  }

  /**
   * @param {Element | HTMLElement | Node} elem - The element to be scrolled into view with delay
   * @param {number} [delayTime = 1000] - How long is the delay
   * @returns {Promise<void>}
   */
  function scrollIntoViewWithDelay(elem, delayTime = 1000) {
    scrollIntoView(elem);
    return delay(delayTime);
  }

  /**
   * @desc Calls the click function on the supplied element if non-null/defined.
   * Returns true or false to indicate if the click happened
   * @param {HTMLElement | Element | Node} elem - The element to be clicked
   * @return {boolean}
   */
  function click(elem) {
    let clicked = false;
    if (elem != null) {
      elem.dispatchEvent(
        new window.MouseEvent('mouseover', {
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

  /**
   * @param {HTMLElement | Element | Node} elem - The element to be clicked
   * @param {number} [delayTime = 1000] - How long is the delay
   * @returns {Promise<boolean>}
   */
  async function clickWithDelay(elem, delayTime = 1000) {
    let clicked = click(elem);
    if (clicked) {
      await delay(delayTime);
    }
    return clicked;
  }

  /**
   * @param {Element | Node | HTMLElement} selectFrom - element to use for the querySelector call
   * @param {string} selector - the css selector to use
   * @param {number} [delayTime = 1000] - How long is the delay
   * @returns {Promise<boolean>}
   */
  function selectElemFromAndClickWithDelay(
    selectFrom,
    selector,
    delayTime = 1000
  ) {
    return clickWithDelay(selectFrom.querySelector(selector), delayTime);
  }

  /**
   * @param {HTMLElement | Element} selectFrom - The element to use to call querySelector(selector) on
   * @param {string} selector - the css selector to use
   * @param {number} n - How many times to click the element returned by
   * performing selectFrom.querySelector(selector)
   * @param {number} [delayTime = 1000] - How long is the delay
   */
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

  if (typeof window.$wbOutlinkSet$ === 'undefined') {
    Object.defineProperty(window, '$wbOutlinkSet$', {
      value: new Set(),
      enumerable: false
    });
  } else {
    window.$wbOutlinkSet$.clear();
  }

  if (typeof window.$wbOutlinks$ === 'undefined') {
    Object.defineProperty(window, '$wbOutlinks$', {
      get() {
        return Array.from(window.$wbOutlinkSet$);
      },
      set() {},
      enumerable: false
    });
  }

  const outlinks = window.$wbOutlinkSet$;
  const goodSchemes = { 'http:': true, 'https:': true };
  const outLinkURLParser = new URL('about:blank');
  const outlinkSelector = 'a[href], area[href]';

  function shouldIgnoreLink(test) {
    let ignored = false;
    let i = ignored.length;
    while (i--) {
      if (test.startsWith(ignored[i])) {
        ignored = true;
        break;
      }
    }
    if (!ignored) {
      let parsed = true;
      try {
        outLinkURLParser.href = test;
      } catch (error) {
        parsed = false;
      }
      return !(parsed && goodSchemes[outLinkURLParser.protocol]);
    }
    return ignored;
  }

  function addOutLinks(toAdd) {
    let href;
    let i = toAdd.length;
    while (i--) {
      href = toAdd[i].href.trim();
      if (href && !outlinks.has(href) && !shouldIgnoreLink(href)) {
        outlinks.add(href);
      }
    }
  }

  function collectOutlinksFrom(queryFrom) {
    addOutLinks(queryFrom.querySelectorAll(outlinkSelector));
  }

  addBehaviorStyle('.wr-debug-visited {border: 6px solid #3232F1;}');

  class InstagramPosts {
    constructor(xpg) {
      this.xpg = xpg;
      /**
       * @desc  Names of internal React properties
       * @type {{multiImages: string, rootContainer: string, internalRoot: string, onDomNode: string, mProps: string}}
       */
      this.reactProps = {
        multiImages: 'sidecarChildren'
      };

      /**
       * @type {Element}
       */
      this.reactRoot = getReactRootHostElem();

      /**
       * @type {Object}
       */
      this.internalRoot = getInternalRootOnElem(this.reactRoot);
      this.profilePage = window._sharedData.entry_data.ProfilePage[0];
      this.userId = this.profilePage.graphql.user.id;
      this.userName = this.profilePage.graphql.user.username;
      /**
       * @desc Property names of keys on react elements
       * @type {{profileKey: string, postGrid: string}}
       */
      this.componentKeys = {
        profileKey: `userprofile_${this.userName}`,
        postGrid: 'virtual_posts_grid'
      };

      /**
       * @desc Query Selectors used
       * @type {{multipleImages: string, hasVideo: string, postTopMostContainer: string, rightChevron: string, postPopupArticle: string, multiImageDisplayDiv: string}}
       */
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

      /**
       * @desc Xpath query selectors used
       * @type {{postPopupClose: string, loadMoreComments: string, showAllComments: string}}
       */
      this.xpathQ = {
        postPopupClose: '//body/div/div/button[contains(text(), "Close")]',
        loadMoreComments: '//li/button[contains(text(), "Load more comments")]',
        showAllComments: '//li/button[contains(text(), "View all")]'
      };

      this.rootProfileNode = null;

      /**
       * @desc The redux used by the user posts application
       * @type {?{getState: function, subscribe: function(listener): function}}
       */
      this.store = null;

      /**
       * @type {Object}
       */
      this.articleInternals = null;
      /**
       * @type {Object}
       */
      this.postGrid = null;
      /**
       * @type {Object}
       */
      this.postScrollContainer = null;
      /**
       * @type {Object}
       */
      this.postWrappingDiv = null;
      /**
       * @type {string}
       */
      this.rowClassName = '';

      this.posts = null;
      this.postsByUserId = null;
      this._unsubscribe = null;

      this.seenPostRows = new Set();
      this._didInit = false;

      this.keyedComponentSelector = this.keyedComponentSelector.bind(this);
    }

    /**
     * @desc Initialize
     */
    init() {
      if (this._didInit) return;
      this._getReduxStore();
      this._getPostLoaderInternals();
      this._didInit = true;
    }

    /**
     * @desc Returns the currently rendered post rows that we have not seen before.
     * Instagram's react application keys the post rows (3 posts per row) with
     * the index of the row out of all rows to be rendered. We use this key
     * to uniquely identify which posts (via row numbers) we have seen.
     * @return {Array<{node: Element, reactInstance: Object}>}
     */
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

    /**
     * @desc Returns an async iterator that yields every post in the users
     * Instagram timeline.
     * @return {AsyncIterator<Element | Node>}
     */
    async *postIterator() {
      let currentPostRows = this.getRenderedPostRows();
      // consume rows until all posts have been loaded
      do {
        yield* this.consumeRow(currentPostRows);
        currentPostRows = this.getRenderedPostRows();
      } while (this.loadedCount < this.totalCount);
      // finish consuming the rows until we are done
      if (currentPostRows.length === 0) {
        currentPostRows = this.getRenderedPostRows();
      }
      do {
        yield* this.consumeRow(currentPostRows);
        currentPostRows = this.getRenderedPostRows();
      } while (currentPostRows.length > 0);
    }

    /**
     * @desc Returns an async iterator that yields each post in the supplied post row.
     * Each the post is clicked and all comments are loaded plus:
     * If the post contains multiple images then all images in the post are visited
     * If the post contains a video then the video is played (uses a HTML video tag)
     * @param {Array<{node: Element, reactInstance: Object}>} postRow
     * @return {AsyncIterator<Element | Node>}
     */
    async *consumeRow(postRow) {
      let row, j, numPosts, post, posts;
      let i = 0,
        numRows = postRow.length;
      for (; i < numRows; ++i) {
        // scroll post row into view
        row = postRow[i];
        if (debug) {
          row.node.classList.add('wr-debug-visited');
        }
        await scrollIntoViewWithDelay(row.node);
        posts = row.node.childNodes;
        numPosts = posts.length;
        // for each post in the row
        for (j = 0; j < numPosts; ++j) {
          post = posts[j];
          collectOutlinksFrom(post);
          // scroll it into view and check what type of post it is
          await scrollIntoViewWithDelay(post);
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

    /**
     * @desc Handles the multi-image posts
     * @param {Element | Node | HTMLElement} post
     */
    async handleMultiImagePost(post) {
      // open the post and get references to the DOM structure of the open post
      const { portal, displayDiv } = await this.openPost(post);
      // get the direct React representation of the display div
      const displayDivReact = reactInstanceFromDOMElem(displayDiv);
      // get the number of images we must display from the child React component
      // of the display div
      const numImages =
        getViaPath(
          displayDivReact,
          'child',
          reactProps.mProps,
          this.reactProps.multiImages,
          'length'
        ) || 100;
      // display each image by clicking the right chevron (next image)
      await selectFromAndClickNTimesWithDelay(
        portal,
        this.selectors.rightChevron,
        numImages
      );
      // load all comments and close the post
      await this.loadAllComments();
      await this.closePost();
    }

    /**
     * @desc Handles posts that contain videos
     * @param {Element | Node | HTMLElement} post
     */
    async handleVideoPost(post) {
      // open the post and get references to the DOM structure of the open post
      const { displayDiv } = await this.openPost(post);
      // select and play the video. The video is a mp4 that is already loaded
      // need to only play it for the length of time we are visiting the post
      // just in case
      await selectElemFromAndClickWithDelay(displayDiv, 'a[role="button"]');
      // load all comments and close the post
      await this.loadAllComments();
      await this.closePost();
    }

    /**
     * @desc Handles posts that are not multi-image or videos
     * @param {Element | Node | HTMLElement} post
     */
    async handleCommentsOnly(post) {
      // open the post and get references to the DOM structure of the open post
      await this.openPost(post);
      // load all comments and close the post
      await this.loadAllComments();
      await this.closePost();
    }

    /**
     * @desc The load more comments button, depending on the number of comments,
     * will contain two variations of text (see {@link xpathQ} for those two
     * variations). Calls {@link getMoreComments} and clicks the button returned
     * as the result of the xpath query until it returns an zero length array.
     * @return {Promise<void>}
     */
    async loadAllComments() {
      let moreComments = this.getMoreComments();
      while (moreComments.length) {
        await clickWithDelay(moreComments[0], 1500);
        moreComments = this.getMoreComments();
      }
    }

    /**
     * @desc Opens the selected post. The post element is a div that contains
     * a direct child that is an anchor tag. The anchor tag is the clickable
     * element not the div. Once the post has been determined to be opened,
     * returns the relevant elements of the open post.
     * @param {Element | Node} post
     * @return {Promise<{portal: Element, displayDiv: Element}>}
     */
    async openPost(post) {
      // click the first child of the post div (a tag)
      await clickWithDelay(post.childNodes[0]);
      // wait for the post portal to open and get a reference to that dom element
      const portal = await waitForAndSelectElement(
        document,
        this.selectors.postPopupArticle
      );
      // get a reference to the post div in the portal
      const displayDiv = portal.querySelector(
        this.selectors.multiImageDisplayDiv
      );
      return { portal, displayDiv };
    }

    /**
     * @desc Closes the post
     * @return {Promise<void>}
     */
    async closePost() {
      const close = this.xpg(this.xpathQ.postPopupClose)[0];
      if (close) {
        await clickWithDelay(close);
      }
    }

    /**
     * @desc Executes the xpath query that selects the load more comments button
     * @return {Array<Element>}
     */
    getMoreComments() {
      // first check for load more otherwise return the results of querying
      // for show all comments
      const moreComments = this.xpg(this.xpathQ.loadMoreComments);
      if (moreComments.length === 0)
        return this.xpg(this.xpathQ.showAllComments);
      return moreComments;
    }

    /**
     * @param {Element | Node | HTMLElement} post
     */
    isMultiImagePost(post) {
      return post.querySelector(this.selectors.multipleImages) != null;
    }

    /**
     * @param {Element | Node | HTMLElement} post
     */
    isVideoPost(post) {
      return post.querySelector(this.selectors.hasVideo) != null;
    }

    /**
     * @return {boolean}
     */
    get hasNextPage() {
      return this.postsByUserId.get(this.userId).pagination.hasNextPage;
    }

    /**
     * @return {boolean}
     */
    get isFetching() {
      return this.postsByUserId.get(this.userId).pagination.isFetching;
    }

    /**
     * @return {number}
     */
    get totalCount() {
      return this.postsByUserId.get(this.userId).count;
    }

    /**
     * @return {number}
     */
    get loadedCount() {
      return this.postsByUserId.get(this.userId).pagination.loadedCount;
    }

    /**
     * @return {AsyncIterator<Element|Node>}
     */
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

    /**
     *
     * @private
     */
    _getPostLoaderInternals() {
      const articleInternals = reactInstanceFromDOMElem(
        document.querySelector(this.selectors.postTopMostContainer)
      );
      let postGrid; // react component: first child of article
      let postScrollContainer; // live div: article > div
      let postWrappingDiv; // live div: article > div > div.style="flex-direction; padding-bottom; padding-top;"
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
})($x, false);
