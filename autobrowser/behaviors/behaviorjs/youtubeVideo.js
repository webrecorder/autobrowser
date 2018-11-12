(function runner(xpg, debug) {
  /**
   * @param {string} xpathQuery
   * @param {Element | Document} startElem
   * @return {XPathResult}
   */

  /**
   * @param {string} selector - the selector to be use
   * @param {Element|Node|HTMLElement|Document} [context] - element to use rather than document for the querySelector call
   * @returns {Element | Node | HTMLElement | HTMLIFrameElement}
   */
  function qs(selector, context) {
    if (context != null) return context.querySelector(selector);
    return document.querySelector(selector);
  }

  /**
   * @param {string} selector - the selector to be use
   * @param {Element | Node | HTMLElement | Document} [context]
   * @returns {NodeList<Element | Node | HTMLElement>}
   */
  function qsa(selector, context) {
    if (context != null) return context.querySelectorAll(selector);
    return document.querySelectorAll(selector);
  }

  /**
   * @param {string} eid
   * @param {?Document} [context]
   * @returns {?HTMLElement}
   */
  function id(eid, context) {
    if (context != null) return context.getElementById(eid);
    return document.getElementById(eid);
  }

  /**
   * @param {HTMLElement | Element | Node} elem
   * @param {string} [marker = 'wrvistited']
   */
  function markElemAsVisited(elem, marker = 'wrvistited') {
    if (elem != null) {
      elem.classList.add(marker);
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
   * @param {Document|Element} elem
   * @param {number} nth
   * @return {?Element}
   */
  function nthChildElemOf(elem, nth) {
    if (elem && elem.children && elem.children.length >= nth) {
      return elem.children[nth - 1];
    }
    return null;
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

  function scrollIntoViewAndWaitFor(elem, predicate) {
    scrollIntoView(elem);
    return waitForPredicate(predicate);
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
   * @param {HTMLElement | Element | Node} elem - The element to be
   * @return {boolean}
   */
  function scrollIntoViewAndClick(elem) {
    scrollIntoView(elem);
    return click(elem);
  }

  /**
   * @param {string} selector
   * @param {Document | Element} [cntx]
   */
  async function selectAndPlay(selector, cntx) {
    const elem = qs(selector, cntx);
    if (elem && elem.paused) {
      await elem.play();
    }
  }

  /**
   * @desc Observe dom mutation using a MutationObserver as a stream (AsyncIterator)
   */
  class MutationStream {
    constructor() {
      this.mo = new MutationObserver((ml, ob) => {
        if (this._resolve) {
          this._resolve(ml);
        }
      });
      this._resolve = null;
      this._loopStream = false;
    }

    /**
     * @param {Node} elem
     * @param {Object} config
     */
    observe(elem, config) {
      this.mo.observe(elem, config);
      this._loopStream = true;
    }

    /**
     * @param {Node} elem
     * @param {Object} config
     * @return {AsyncIterableIterator<MutationRecord[]>}
     */
    observeStream(elem, config) {
      this.observe(elem, config);
      return this.streamItr();
    }

    /**
     * @desc Creates a conditional mutation stream. If the startPredicate
     * does not return true then the the observer discontents ending the stream.
     * Otherwise the stream continues to emit mutations until the observer is
     * disconnected or the stopPredicate returns true. The stopPredicate is polled
     * at 1.5 second intervals when the observer is waiting for the next mutation.
     * @param {Node} elem
     * @param {Object} config
     * @param {function(): boolean} startPredicate
     * @param {function(): boolean} stopPredicate
     * @return {AsyncIterableIterator<MutationRecord[]>}
     */
    predicatedStream(elem, config, startPredicate, stopPredicate) {
      this.observe(elem, config);
      return this.predicateStreamItr(startPredicate, stopPredicate);
    }

    disconnect() {
      this.mo.disconnect();
      this._loopStream = false;
      if (this._resolve) {
        this._resolve(null);
      }
      this._resolve = null;
    }

    /**
     * @return {Promise<?MutationRecord[]>}
     * @private
     */
    _getNext() {
      return new Promise(resolve => {
        this._resolve = resolve;
      });
    }

    /**
     * @return {AsyncIterableIterator<MutationRecord[]>}
     */
    async *streamItr() {
      while (this._loopStream) {
        let next = await this._getNext();
        if (next == null) {
          break;
        }
        yield next;
      }
      this.disconnect();
    }

    /**
     * @desc Returns an mutation stream that ends if the startPredicate returns false
     * otherwise keeps the stream alive until disconnect or the stopPredicate, polled
     * at 1.5 second intervals when waiting for next mutation, returns false.
     * Automatically disconnects at the end.
     * @param {function(): boolean} startPredicate
     * @param {function(): boolean} stopPredicate
     * @return {AsyncIterableIterator<?MutationRecord[]>}
     */
    async *predicateStreamItr(startPredicate, stopPredicate) {
      if (!startPredicate()) {
        return this.disconnect();
      }
      while (this._loopStream) {
        let checkTo;
        let next = await Promise.race([
          this._getNext(),
          new Promise(resolve => {
            checkTo = setInterval(() => {
              if (stopPredicate()) {
                clearInterval(checkTo);
                return resolve(null);
              }
            }, 1500);
          })
        ]);
        if (checkTo) clearInterval(checkTo);
        if (next == null) {
          break;
        }
        yield next;
      }
      this.disconnect();
    }

    /**
     * @return {AsyncIterableIterator<?MutationRecord[]>}
     */
    [Symbol.asyncIterator]() {
      return this.streamItr();
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

  const selectors = {
    videoInfoMoreId: 'more',
    loadMoreComments: 'div[slot="more-button"] > paper-button',
    showMoreReplies: 'yt-next-continuation > paper-button',
    commentRenderer: 'ytd-comment-thread-renderer',
    commentsContainerId: 'comments',
    loadedReplies: 'div[id="loaded-replies"]',
    loadingCommentsSpinner:
      '#continuations > yt-next-continuation > paper-spinner',
    outlinks: 'ytd-thumbnail > a[id="thumbnail"]'
  };

  const mutationConf = { attributes: false, childList: true, subtree: false };

  function loadMoreComments(cRenderer, selector) {
    const more = qs(selector, cRenderer);
    if (more && !more.hidden) {
      return scrollIntoViewAndClick(more);
    }
    return false;
  }

  /**
   *
   * @param {MutationStream} mStream
   * @param renderer
   * @return {Promise<void>}
   */
  async function viewAllReplies(mStream, renderer) {
    const replies = qs(selectors.loadedReplies, renderer);
    if (replies != null) {
      // console.log('rendered has replies', replies);
      let mutation;
      for await (mutation of mStream.predicatedStream(
        replies,
        mutationConf,
        () => loadMoreComments(renderer, selectors.loadMoreComments),
        () => !selectorExists(selectors.showMoreReplies, renderer)
      )) {
        // console.log(mutation);
        await scrollIntoViewWithDelay(replies.lastChild, 750);
        if (!loadMoreComments(renderer, selectors.showMoreReplies)) {
          mStream.disconnect();
          break;
        }
      }
      // console.log('consumed all renderer comments', renderer);
    }
  }

  function nextComment(elem) {
    const next = elem.nextElementSibling;
    elem.remove();
    return next;
  }

  async function* playVideoAndLoadComments() {
    // async function playVideoAndLoadComments() {
    await selectAndPlay('video');
    const videoInfo = id(selectors.videoInfoMoreId);
    if (videoInfo && !videoInfo.hidden) {
      await clickWithDelay(videoInfo);
    }
    await scrollIntoViewAndWaitFor(id(selectors.commentsContainerId), () =>
      selectorExists(selectors.commentRenderer)
    );
    const relatedVideos = nthChildElemOf(id('related'), 2);
    if (relatedVideos) {
      addOutLinks(qsa(selectors.outlinks, relatedVideos));
    }
    const commentsContainer = qs('#comments > #sections > #contents');
    const mStream = new MutationStream();
    let comment = commentsContainer.children[0];
    let numLoadedComments = commentsContainer.children.length;
    while (comment != null) {
      // console.log('viewing comment', comment);
      markElemAsVisited(comment);
      await scrollIntoViewWithDelay(comment);
      await viewAllReplies(mStream, comment);
      numLoadedComments = commentsContainer.children.length;
      if (comment.nextElementSibling == null) {
        // console.log('waiting for more comments to load');
        await waitForAdditionalElemChildren(
          commentsContainer,
          numLoadedComments
        );
        // console.log(
        //   `next loaded size ${numLoadedComments}, next comment = `,
        //   comment.nextElementSibling
        // );
      }
      yield comment;
      comment = nextComment(comment);
    }
  }

  window.$WRIterator$ = playVideoAndLoadComments();
  window.$WRIteratorHandler$ = async function() {
    const next = await $WRIterator$.next();
    return next.done;
  };

  // playVideoAndLoadComments().then(() => console.log('done'));
})($x, true);
