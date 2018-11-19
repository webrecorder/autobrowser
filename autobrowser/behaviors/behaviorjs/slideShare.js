(function runner(xpg, debug) {
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
   * @param {HTMLIFrameElement} iframe
   * @return {boolean}
   */
  function canAcessIf(iframe) {
    if (iframe == null) return false;
    try {
      iframe.contentWindow.window;
    } catch (e) {
      return false;
    }
    return iframe.contentDocument != null;
  }

  /**
   * @param {function(xpathQuery: string, startElem: ?Node): Node[]} xpg
   * @param {string} tag
   * @param {function(elem: Node): boolean} predicate
   * @param {Document} [cntx]
   * @return {?Element|?HTMLIFrameElement|?Node}
   */
  function findTag(xpg, tag, predicate, cntx) {
    const tags = xpg(`//${tag}`, cntx || document);
    const len = tags.length;
    let i = 0;
    for (; i < len; ++i) {
      if (predicate(tags[i])) return tags[i];
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
   * @desc Calls the click function on the supplied element if non-null/defined.
   * Returns true or false to indicate if the click happened
   * @param {HTMLElement | Element | Node} elem - The element to be clicked
   * @param {Window} cntx - The context window
   * @return {boolean}
   */
  function clickInContext(elem, cntx) {
    let clicked = false;
    if (elem != null) {
      elem.dispatchEvent(
        new cntx.MouseEvent('mouseover', {
          view: cntx,
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
   * @param {Window} cntx - The context window
   * @param {number} [delayTime = 1000] - How long is the delay
   * @returns {Promise<boolean>}
   */
  async function clickInContextWithDelay(elem, cntx, delayTime = 1000) {
    let clicked = clickInContext(elem, cntx);
    if (clicked) {
      await delay(delayTime);
    }
    return clicked;
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
   * @desc Retrieves the property of an object, or item in array at index, based
   * on the supplied path.
   * @example
   *   const obj = { a: { b: { c: [1, 2, 3] } } }
   *   const two = getViaPath(obj, 'a', 'b', 'c', 1); // two == 2
   * @param {Object | Array | Element | Node} obj
   * @param {string | number} pathItems
   * @return {any}
   */

  function sendAutoFetchWorkerURLs(urls) {
    if (window.$WBAutoFetchWorker$) {
      window.$WBAutoFetchWorker$.justFetch(urls);
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

  /**
   * @param {HTMLAnchorElement|HTMLAreaElement|string} elemOrString
   */
  function addOutlink(elemOrString) {
    const href = (elemOrString.href || elemOrString).trim();
    if (href && !outlinks.has(href) && !shouldIgnoreLink(href)) {
      outlinks.add(href);
    }
  }

  const selectors = {
    iframeLoader: 'iframe.ssIframeLoader',
    nextSlide: 'btnNext',
    slideContainer: 'div.slide_container',
    showingSlide: 'div.slide.show',
    divSlide: 'div.slide',
    sectionSlide: 'section.slide',
    slideImg: 'img.slide_image',
    relatedDecks: 'div.tab.related-tab',
    moreComments: 'a.j-more-comments'
  };

  const isSlideShelfIF = _if => _if.src.endsWith('/slideshelf');

  /**
   * @param {Document | Element} doc
   * @param {string} slideSelector
   * @return {number}
   */
  function getNumSlides(doc, slideSelector) {
    const slideContainer = qs(selectors.slideContainer, doc);
    if (slideContainer) {
      return qsa(slideSelector, doc).length;
    }
    return -1;
  }

  /**
   * @param {Document} doc
   */
  function extracAndPreserveSlideImgs(doc) {
    const imgs = qsa(selectors.slideImg, doc);
    const len = imgs.length;
    const toFetch = [];
    let i = 0;
    let imgDset;
    for (; i < len; ++i) {
      imgDset = imgs[i].dataset;
      if (imgDset) {
        toFetch.push(imgDset.full);
        toFetch.push(imgDset.normal);
        toFetch.push(imgDset.small);
      }
    }
    sendAutoFetchWorkerURLs(toFetch);
  }

  /**
   * @param {Window} win
   * @param {Document} doc
   * @param {string} slideSelector
   * @return {Promise<void>}
   */
  async function consumeSlides(win, doc, slideSelector) {
    extracAndPreserveSlideImgs(doc);
    const numSlides = getNumSlides(doc, slideSelector);
    let i = 1;
    for (; i < numSlides; ++i) {
      await clickInContextWithDelay(id(selectors.nextSlide, doc), win);
    }
    await clickInContextWithDelay(id(selectors.nextSlide, doc), win);
  }

  /**
   * @return {AsyncIterableIterator<*>}
   */
  async function* handleSlideDeck() {
    yield await consumeSlides(window, document, selectors.sectionSlide);
  }

  /**
   * @param {Window} win
   * @param {Document} doc
   * @return {AsyncIterableIterator<*>}
   */
  async function* doSlideShowInFrame(win, doc) {
    const decks = qsa('li', qs(selectors.relatedDecks, doc));
    const numDecks = decks.length;
    const deckIF = qs(selectors.iframeLoader, doc);
    yield await consumeSlides(
      deckIF.contentWindow,
      deckIF.contentDocument,
      selectors.divSlide
    );
    let i = 1;
    for (; i < numDecks; ++i) {
      await new Promise(r => {
        const loaded = () => {
          deckIF.removeEventListener('load', loaded);
          r();
        };
        deckIF.addEventListener('load', loaded);
        addOutlink(decks[i].firstElementChild);
        clickInContext(decks[i].firstElementChild, win);
      });
      yield await consumeSlides(
        deckIF.contentWindow,
        deckIF.contentDocument,
        selectors.divSlide
      );
    }
  }

  /**
   * @return {AsyncIterableIterator<*>}
   */
  function init() {
    if (canAcessIf(qs(selectors.iframeLoader))) {
      // 'have iframe loader in top'
      return doSlideShowInFrame(window, document);
    }
    const maybeIF = findTag(maybePolyfillXPG(xpg), 'iframe', isSlideShelfIF);
    if (maybeIF && canAcessIf(maybeIF)) {
      // have slideself loader in top
      return doSlideShowInFrame(maybeIF.contentWindow, maybeIF.contentDocument);
    }
    // have slides in top
    return handleSlideDeck();
  }

  window.$WRIterator$ = init();
  window.$WRIteratorHandler$ = async function() {
    const next = await $WRIterator$.next();
    return next.done;
  };
})($x, true);
