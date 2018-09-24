(async function(xpg) {
  if (
    typeof xpg !== 'function' ||
    xpg.toString().indexOf('[Command Line API]') === -1
  ) {
    /**
     * @desc Polyfill console api $x
     * @param {string} xpathQuery
     * @param {Element | Document} startElem
     * @return {Array<HTMLElement>}
     */
    xpg = function(xpathQuery, startElem) {
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

  /**
   *
   * @param {Object | Array | Element | Node} obj
   * @param {string | number} pathItems
   * @return {Any}
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

  /**
   *
   * @param {string} selector
   * @param {Element | Node} fromNode
   * @return {Element | Node}
   */
  async function waitForAndSelectElement(selector, fromNode) {
    let elem = fromNode.querySelector(selector);
    if (!elem) {
      await waitForPredicate(() => fromNode.querySelector(selector) != null);
      elem = fromNode.querySelector(selector);
    }
    return elem;
  }

  /**
   * @typedef {Object} Store
   * @property {function(): Object} getState
   * @property {function(listener): function()} subscribe
   */

  class InstagramPosts {
    constructor(xpg) {
      this.xpg = xpg;
      this.reactProps = {
        multiImages: 'sidecarChildren',
        rootContainer: '_reactRootContainer',
        internalRoot: '_internalRoot',
        onDomNode: '__reactInternalInstance',
        mProps: 'memoizedProps'
      };
      this.reactRoot = document.getElementById('react-root')[
        this.reactProps.rootContainer
      ];
      this.internalRoot = this.reactRoot[this.reactProps.internalRoot];
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
        showAllComments:
          '//li/button[contains(text(), "View all") and contains(text(), "comments")]'
      };

      this.rootProfileNode = null;
      /**
       *
       * @type {?Store}
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
      this.seenPosts = new Set();
      this._didInit = false;
      this.scrollBehavior = {
        behavior: 'auto',
        block: 'center',
        inline: 'center'
      };
    }

    init() {
      if (this._didInit) return;
      this._getReduxStore();
      this._getPostLoaderInternals();
      this._didInit = true;
    }

    /**
     * @return {Array<{node: Element, reactInstance: Object}>}
     */
    getRenderedPostRows() {
      const nodes = this.postWrappingDiv.stateNode.childNodes;
      const renderedNodes = [];
      const length = nodes.length;
      let i = 0;
      let node;
      let reactInstance;
      for (; i < length; ++i) {
        node = nodes[i];
        reactInstance = this._reactInstanceFromDOMElem(node);
        if (!this.seenPostRows.has(reactInstance.key)) {
          this.seenPostRows.add(reactInstance.key);
          renderedNodes.push({ node, reactInstance });
        }
      }
      return renderedNodes;
    }

    /**
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
     *
     * @param {Array<{node: Element, reactInstance: Object}>} postRow
     * @return {AsyncIterator<Element | Node>}
     */
    async *consumeRow(postRow) {
      let row, i, numPosts, post, posts;
      while (postRow.length > 0) {
        row = postRow.shift();
        await this.scrollIntoView(row.node);
        posts = row.node.childNodes;
        numPosts = posts.length;
        for (i = 0; i < length; ++i) {
          post = posts[i];
          await this.scrollIntoView(post);
          if (this.isMultiImagePost(post)) {
            await this.handleMultiImagePost(post);
          } else if (this.isVideoPost(post)) {
            await this.handleVideoPost(post);
          }
          yield post;
        }
      }
    }

    /**
     * @param {Element | Node | HTMLElement} post
     */
    async handleMultiImagePost(post) {
      await this.clickWithDelay(post.childNodes[0]);
      let portal = await waitForAndSelectElement(
        this.selectors.postPopupArticle,
        document
      );
      const displayDiv = portal.querySelector(
        this.selectors.multiImageDisplayDiv
      );
      const displayDivReact = this._reactInstanceFromDOMElem(displayDiv);
      const numImages =
        getViaPath(
          displayDivReact,
          'child',
          this.reactProps.mProps,
          this.reactProps.multiImages,
          'length'
        ) || 100;
      let i = 0;
      let clickMe;
      for (; i < numImages; ++i) {
        clickMe = portal.querySelector(this.selectors.rightChevron);
        if (clickMe) {
          await this.clickWithDelay(clickMe);
        }
      }
      let moreComments = this.getMoreComments();
      while (moreComments.length) {
        await this.clickWithDelay(moreComments[0]);
        moreComments = this.getMoreComments();
      }
      const close = this.xpg(this.xpathQ.postPopupClose)[0];
      if (close) {
        await this.clickWithDelay(close);
      }
    }

    /**
     * @param {Element | Node | HTMLElement} post
     */
    async handleVideoPost(post) {
      await this.clickWithDelay(post.childNodes[0]);
      let portal = await waitForAndSelectElement(
        this.selectors.postPopupArticle,
        document
      );
      const displayDiv = portal.querySelector(
        this.selectors.multiImageDisplayDiv
      );
      const video = displayDiv.querySelector('video');
      await video.play();
      let moreComments = this.getMoreComments();
      while (moreComments.length) {
        await this.clickWithDelay(moreComments[0]);
        moreComments = this.getMoreComments();
      }
      const close = this.xpg(this.xpathQ.postPopupClose)[0];
      if (close) {
        await this.clickWithDelay(close);
      }
    }

    getMoreComments() {
      let moreComments = this.xpg(this.xpathQ.loadMoreComments);
      if (!moreComments) return this.xpg(this.xpathQ.showAllComments);
      return moreComments;
    }

    /**
     * @param {Element | Node | HTMLElement} elem
     * @param {number} [delayTime = 1000]
     */
    clickWithDelay(elem, delayTime = 1000) {
      elem.click();
      return this.delay(delayTime);
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
     * @param {number} [delayTime = 1000]
     */
    delay(delayTime = 3000) {
      return new Promise(r => setTimeout(r, delayTime));
    }

    /**
     * @param {Element | Node | HTMLElement} elem
     * @param {number} [delayTime = 1000]
     */
    scrollIntoView(elem, delayTime = 1000) {
      elem.scrollIntoView(this.scrollBehavior);
      return this.delay(delayTime);
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

    /**
     * @param {Element | Node} elem
     * @return {Object}
     */
    _reactInstanceFromDOMElem(elem) {
      const keys = Object.keys(elem);
      let i = 0;
      let len = keys.length;
      let internalKey;
      while (i < len) {
        if (keys[i].startsWith(this.reactProps.onDomNode)) {
          internalKey = keys[i];
          break;
        }
        i += 1;
      }
      if (!internalKey) throw new Error('Could not find react internal key');
      return elem[internalKey];
    }

    _getReduxStore() {
      let child = this.internalRoot.current.child;
      let rootProfileNode;
      while (child) {
        if (child.key && child.key === this.componentKeys.profileKey) {
          rootProfileNode = child;
          break;
        }
        child = child.child;
      }
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
      const articleInternals = this._reactInstanceFromDOMElem(
        document.querySelector(this.selectors.postTopMostContainer)
      );
      let postGrid; // react component: first child of article
      let postScrollContainer; // live div: article > div
      let postWrappingDiv; // live div: article > div > div.style="flex-direction; padding-bottom; padding-top;"
      let child = articleInternals.child;
      let rowClassName;
      while (child) {
        if (child.key === this.componentKeys.postGrid) postGrid = child;
        if (child.type === 'div') {
          postScrollContainer = child;
          let nextChild = child.child;
          if (nextChild && nextChild.sibling) {
            postWrappingDiv = nextChild.sibling;
          }
          break;
        }
        if (child[this.reactProps.mProps] && child[this.reactProps.mProps].rowClassName) {
          rowClassName = child[this.reactProps.mProps].rowClassName;
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

  const instaPosts = new InstagramPosts(xpg);
  window.$WRTLIterator$ = instaPosts.postIterator();
  window.$WRIteratorHandler$ = async function() {
    const next = await $WRTLIterator$.next();
    return next.done;
  };
})($x);
