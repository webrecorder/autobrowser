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

  /**
   * @param {Element} parentElement
   * @param {number} currentChildCount
   * @param {{pollRate: number, max: number}} [opts]
   * @return {Promise<void>}
   */
  function waitForAdditionalElemChildren(
    parentElement,
    currentChildCount,
    opts
  ) {
    let pollRate = 1000;
    let max = 6;
    if (opts != null) {
      if (opts.pollRate != null) pollRate = opts.pollRate;
      if (opts.max != null) max = opts.max;
    }
    let n = 0;
    let int = -1;
    return new Promise(resolve => {
      int = setInterval(() => {
        if (!parentElement.isConnected) {
          clearInterval(int);
          return resolve();
        }
        if (
          parentElement.children &&
          parentElement.children.length > currentChildCount
        ) {
          clearInterval(int);
          return resolve();
        }
        if (n > max) {
          clearInterval(int);
          return resolve();
        }
        n += 1;
      }, pollRate);
    });
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
  function getReactRootContainer(elem) {
    const hostContainer = elem[reactProps.rootContainer];
    if (hostContainer) {
      return hostContainer[reactProps.internalRoot];
    }
    throw new Error('cant get internal root on host contianer');
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
   * performing selectFrom.querySelector(selector)
   * @param {Object} [opts = {}] - options about delayTime and safety time
   */
  async function selectFromAndClickUntilNullWithDelay(
    selectFrom,
    selector,
    opts = {}
  ) {
    const delayTime = opts.delayTime || 1000;
    let exit = false;
    let safety;
    if (opts.safety) {
      safety = setTimeout(() => {
        exit = true;
      }, opts.safety);
    }
    let clickMe = selectFrom.querySelector(selector);
    while (clickMe != null) {
      if (exit) break;
      await clickWithDelay(clickMe, delayTime);
      clickMe = selectFrom.querySelector(selector);
    }
    if (opts.safety) {
      clearTimeout(safety);
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

  const multiImageClickOpts = { safety: 30 * 1000, delayTime: 1000 };

  const selectors = {
    multipleImages: 'span.coreSpriteSidecarIconLarge',
    postTopMostContainer: 'article',
    rightChevron: 'button > div.coreSpriteRightChevron',
    postPopupArticle: `${new Array(3)
      .fill(0)
      .map(() => 'div[role="dialog"]')
      .join(' > ')} > article`,
    multiImageDisplayDiv: 'div > div[role="button"]'
  };

  const videoPostSelectors = [
    'span.coreSpriteVideoIconLarge',
    'span[aria-label$="Video"]',
    'span[class*="glyphsSpriteVideo_large"]'
  ];

  const xpathQ = {
    postPopupClose: '//body/div/div/button[contains(text(), "Close")]',
    loadMoreComments: '//li/button[contains(text(), "Load more comments")]',
    showAllComments: '//li/button[contains(text(), "View all")]'
  };

  /**
   *
   * @param rootProfileNode
   * @return {?Object}
   */
  function extractReduxStore(rootProfileNode) {
    const store = getViaPath(rootProfileNode, 'stateNode', 'context', 'store');
    if (store == null || typeof store.getState === 'undefined') return null;
    let currentState = store.getState();
    if (currentState.posts == null) return null;
    let posts = currentState.posts;
    let postsByUserId = getViaPath(currentState, 'profilePosts', 'byUserId');
    if (postsByUserId == null) return null;
    return {
      store,
      posts,
      postsByUserId
    };
  }

  /**
   * @param componentKeys
   * @return {?Object}
   */
  function getPostLoaderInternals(componentKeys) {
    const articleInternals = reactInstanceFromDOMElem(
      document.querySelector(selectors.postTopMostContainer)
    );
    if (articleInternals == null) return null;
    let postGrid; // react component: first child of article
    let postScrollContainer; // live div: article > div
    let postWrappingDiv; // live div: article > div > div.style="flex-direction; padding-bottom; padding-top;"
    let child = articleInternals.child;
    let rowClassName;
    let nextChild;
    while (child) {
      if (child.key === componentKeys.postGrid) postGrid = child;
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
    if (postGrid == null) return null;
    if (postScrollContainer == null) return null;
    if (postWrappingDiv == null) return null;
    if (rowClassName == null) return null;
    return {
      articleInternals,
      postGrid,
      postScrollContainer,
      postWrappingDiv,
      rowClassName
    };
  }

  /**
   * @return {?Object}
   */
  function setupForReactStrat() {
    const profileInfo = getViaPath(
      window,
      '_sharedData',
      'entry_data',
      'ProfilePage',
      0
    );
    if (profileInfo == null) return null;
    const user = getViaPath(profileInfo, 'graphql', 'user');
    if (user == null) return null;
    const profileUserName = user.username;
    if (profileUserName == null) return null;
    const userId = user.id;
    if (userId == null) return null;
    const instaComponentKeys = {
      profileKey: `userprofile_${profileUserName}`,
      postGrid: 'virtual_posts_grid'
    };
    const reactRoot = getReactRootHostElem();
    if (reactRoot == null) return null;
    const internalRoot = getReactRootContainer(reactRoot);
    if (internalRoot == null) return null;
    const rootProfileNode = findChildWithKey(
      internalRoot.current,
      instaComponentKeys.profileKey
    );
    if (rootProfileNode == null) return null;
    const extractedStore = extractReduxStore(rootProfileNode);
    if (extractedStore == null) return null;
    const postLoadingInfo = getPostLoaderInternals(instaComponentKeys);
    if (postLoadingInfo == null) return null;

    const seenPostRows = new Set();

    const keyedComponentSelector = key => {
      const select = !seenPostRows.has(key);
      if (select) {
        seenPostRows.add(key);
      }
      return select;
    };

    return {
      /**
       * @return {Array<{node: (HTMLElement|Element|Node), reactInstance: Object}>}
       */
      getRenderedPostRows() {
        return reactInstancesFromElements(
          this.postWrappingDiv.stateNode.childNodes,
          keyedComponentSelector
        );
      },
      hasNextPage() {
        return this.postsByUserId.get(this.userId).pagination.hasNextPage;
      },
      isFetching() {
        return this.postsByUserId.get(this.userId).pagination.isFetching;
      },
      totalCount() {
        return this.postsByUserId.get(this.userId).count;
      },
      loadedCount() {
        return this.postsByUserId.get(this.userId).pagination.loadedCount;
      },
      _storeListener() {
        let nextState = this.store.getState();
        if (this.postsByUserId !== nextState.profilePosts.byUserId) {
          this.posts = nextState.posts;
          this.postsByUserId = nextState.profilePosts.byUserId;
          console.log(
            `isFetching=${this.isFetching()}, hasNextPage=${this.hasNextPage()}, loadedCount=${this.loadedCount()}`
          );
        }
      },
      componentKeys: instaComponentKeys,
      seenPostRows,
      reactRoot,
      internalRoot,
      rootProfileNode,
      profileUserName,
      userId,
      ...extractedStore,
      ...postLoadingInfo
    };
  }

  /**
   * @param {Element | Node | HTMLElement} post
   * @return {boolean}
   */
  function isVideoPost(post) {
    let i = 0;
    let len = videoPostSelectors.length;
    for (; i < len; ++i) {
      if (post.querySelector(videoPostSelectors[i]) != null) {
        return true;
      }
    }
    return false;
  }

  /**
   * @param {Element | Node | HTMLElement} post
   */
  function isMultiImagePost(post) {
    return post.querySelector(selectors.multipleImages) != null;
  }

  /**
   * @desc Opens the selected post. The post element is a div that contains
   * a direct child that is an anchor tag. The anchor tag is the clickable
   * element not the div. Once the post has been determined to be opened,
   * returns the relevant elements of the open post.
   * @param {Element | Node} post
   * @return {Promise<{portal: Element, displayDiv: Element}>}
   */
  async function openPost(post) {
    // click the first child of the post div (a tag)
    await clickWithDelay(post.childNodes[0]);
    // wait for the post portal to open and get a reference to that dom element
    const portal = await waitForAndSelectElement(
      document,
      selectors.postPopupArticle
    );
    // get a reference to the post div in the portal
    const displayDiv = portal.querySelector(selectors.multiImageDisplayDiv);
    return { portal, displayDiv };
  }

  /**
   * @desc Closes the post
   * @param xpg
   * @return {Promise<void>}
   */
  async function closePost(xpg) {
    const close = xpg(xpathQ.postPopupClose)[0];
    if (close) {
      await clickWithDelay(close);
    }
  }

  /**
   * @desc Executes the xpath query that selects the load more comments button
   * @param xpg
   * @return {Array<Element>}
   */
  function getMoreComments(xpg) {
    // first check for load more otherwise return the results of querying
    // for show all comments
    const moreComments = xpg(xpathQ.loadMoreComments);
    if (moreComments.length === 0) return xpg(xpathQ.showAllComments);
    return moreComments;
  }

  /**
   * @desc The load more comments button, depending on the number of comments,
   * will contain two variations of text (see {@link xpathQ} for those two
   * variations). Calls {@link getMoreComments} and clicks the button returned
   * as the result of the xpath query until it returns an zero length array.
   * @param xpg
   * @return {Promise<void>}
   */
  async function loadAllComments(xpg) {
    let moreComments = getMoreComments(xpg);
    while (moreComments.length) {
      await clickWithDelay(moreComments[0], 1500);
      moreComments = getMoreComments(xpg);
    }
  }

  /**
   * @desc Handles the multi-image posts
   * @param {Element | Node | HTMLElement} post
   * @param xpg
   */
  async function handleMultiImagePost(post, xpg) {
    // open the post and get references to the DOM structure of the open post
    const { portal } = await openPost(post);
    // display each image by clicking the right chevron (next image)
    await selectFromAndClickUntilNullWithDelay(
      portal,
      selectors.rightChevron,
      multiImageClickOpts
    );
    // load all comments and close the post
    await loadAllComments(xpg);
    await closePost(xpg);
  }

  /**
   * @desc Handles posts that contain videos
   * @param {Element | Node | HTMLElement} post
   * @param xpg
   */
  async function handleVideoPost(post, xpg) {
    // open the post and get references to the DOM structure of the open post
    const { displayDiv } = await openPost(post);
    // select and play the video. The video is a mp4 that is already loaded
    // need to only play it for the length of time we are visiting the post
    // just in case
    await selectElemFromAndClickWithDelay(displayDiv, 'a[role="button"]');
    // load all comments and close the post
    await loadAllComments(xpg);
    await closePost(xpg);
  }

  /**
   * @desc Handles posts that are not multi-image or videos
   * @param {Element | Node | HTMLElement} post
   * @param xpg
   */
  async function handleCommentsOnly(post, xpg) {
    // open the post and get references to the DOM structure of the open post
    await openPost(post);
    // load all comments and close the post
    await loadAllComments(xpg);
    await closePost(xpg);
  }

  async function handlePost(post, xpg) {
    collectOutlinksFrom(post);
    // scroll it into view and check what type of post it is
    await scrollIntoViewWithDelay(post);
    if (isMultiImagePost(post)) {
      await handleMultiImagePost(post, xpg);
    } else if (isVideoPost(post)) {
      await handleVideoPost(post, xpg);
    } else {
      await handleCommentsOnly(post, xpg);
    }
  }

  /**
   * @desc Returns an async iterator that yields each post in the supplied post row.
   * Each the post is clicked and all comments are loaded plus:
   * If the post contains multiple images then all images in the post are visited
   * If the post contains a video then the video is played (uses a HTML video tag)
   * @param {Array<{node: Element}>} postRow
   * @param xpg
   * @return {AsyncIterator<Element | Node>}
   */
  async function* consumeRowReact(postRow, xpg) {
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
        await handlePost(post, xpg);
        yield post;
      }
    }
  }

  async function* postIteratorReact(extractReactStuff, xpg) {
    let currentPostRows = extractReactStuff.getRenderedPostRows();
    // consume rows until all posts have been loaded
    do {
      yield* consumeRowReact(currentPostRows, xpg);
      currentPostRows = extractReactStuff.getRenderedPostRows();
    } while (extractReactStuff.loadedCount < extractReactStuff.totalCount);
    // finish consuming the rows until we are done
    if (currentPostRows.length === 0) {
      currentPostRows = extractReactStuff.getRenderedPostRows();
    }
    do {
      yield* consumeRowReact(currentPostRows, xpg);
      currentPostRows = extractReactStuff.getRenderedPostRows();
    } while (currentPostRows.length > 0);
  }

  async function* instagramFallback(xpg) {
    const scrolDiv = document.querySelector(selectors.postTopMostContainer);
    let reactGarbageDiv = scrolDiv.firstElementChild;
    if (reactGarbageDiv == null)
      throw new Error('Could not first div under article');
    const postRowContainer = reactGarbageDiv.firstElementChild;
    let posts;
    let post;
    let i = 0;
    let row = postRowContainer.firstElementChild;
    let numLoadedRows = postRowContainer.children.length;
    while (row != null) {
      if (debug) {
        row.classList.add('wr-debug-visited');
      }
      await scrollIntoViewWithDelay(row);
      posts = row.childNodes;
      numPosts = posts.length;
      // for each post in the row
      for (i = 0; i < numPosts; ++i) {
        post = posts[i];
        await handlePost(post, xpg);
        yield post;
      }
      numLoadedRows = postRowContainer.children.length;
      if (row.nextElementSibling == null) {
        await waitForAdditionalElemChildren(postRowContainer, numLoadedRows);
      }
      row = row.nextElementSibling;
    }
  }

  const reactSetup = setupForReactStrat();
  if (reactSetup != null) {
    window.$WRTLIterator$ = postIteratorReact(
      reactSetup,
      maybePolyfillXPG(xpg)
    );
  } else {
    window.$WRTLIterator$ = instagramFallback(maybePolyfillXPG(xpg));
  }

  window.$WRIteratorHandler$ = async function() {
    const next = await $WRTLIterator$.next();
    return next.done;
  };

  // async function t() {
  //   for await (let next of window.$WRTLIterator$) {
  //     console.log(next)
  //   }
  // }
  // return t();
})($x, true);
