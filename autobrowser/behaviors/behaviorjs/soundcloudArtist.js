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
   * @param {HTMLElement | Element | Node} elem
   * @param {string} [marker = 'wrvistited']
   */
  function markElemAsVisited(elem, marker = 'wrvistited') {
    if (elem != null) {
      elem.classList.add(marker);
    }
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
   * @param {number} [delayTime = 3000]
   * @returns {Promise<void>}
   */
  function delay(delayTime = 3000) {
    return new Promise(resolve => {
      setTimeout(resolve, delayTime);
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
   * @returns {boolean}
   */
  function selectElemFromAndClick(selectFrom, selector) {
    return click(selectFrom.querySelector(selector));
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

  const xpQueries = {
    soundItem:
      '//div[@class="userStreamItem" and not(contains(@class, "wrvistited"))]'
  };

  const selectors = {
    loadMoreTracks: 'a.compactTrackList__moreLink',
    playSingleTrack: 'a.playButton',
    multiTrackItem: 'li.compactTrackList__item',
    playMultiTrackTrack: 'div.compactTrackListItem.clickToPlay'
  };

  function needToLoadMoreTracks(elem) {
    return elem.querySelector(selectors.loadMoreTracks) != null;
  }

  async function* playMultipleTracks(elem) {
    const tracks = elem.querySelectorAll(selectors.multiTrackItem);
    let i = 0;
    let len = tracks.length;
    if (len === 0) {
      yield false;
      return;
    }
    let playable;
    for (; i < len; ++i) {
      playable = tracks[i];
      markElemAsVisited(playable);
      if (debug) playable.classList.add('wr-debug-visited');
      await scrollIntoViewWithDelay(playable);
      yield selectElemFromAndClick(playable, selectors.playMultiTrackTrack);
    }
  }

  async function* vistSoundItems(xpathGenerator) {
    let snapShot = xpathGenerator(xpQueries.soundItem);
    let soundItem;
    let i, len;
    if (snapShot.length === 0) return;
    do {
      len = snapShot.length;
      i = 0;
      for (; i < len; ++i) {
        soundItem = snapShot[i];
        markElemAsVisited(soundItem);
        collectOutlinksFrom(soundItem);
        if (debug) soundItem.classList.add('wr-debug-visited');
        await scrollIntoViewWithDelay(soundItem);
        if (needToLoadMoreTracks(soundItem)) {
          await selectElemFromAndClickWithDelay(
            soundItem,
            selectors.loadMoreTracks
          );
          yield* playMultipleTracks(soundItem);
        } else {
          yield selectElemFromAndClick(soundItem, selectors.playSingleTrack);
        }
      }
      snapShot = xpathGenerator(xpQueries.soundItem);
      if (snapShot.length === 0) {
        await delay();
        snapShot = xpathGenerator(xpQueries.soundItem);
      }
    } while (snapShot.length > 0);
  }

  window.$WRIterator$ = vistSoundItems(maybePolyfillXPG(xpg));
  window.$WRIteratorHandler$ = async function() {
    const results = await $WRIterator$.next();
    return { done: results.done, wait: results.value };
  };
})($x, false);
