(function runner(xpg, debug) {
  /**
   * @param {string} xpathQuery
   * @param {Element | Document} startElem
   * @return {XPathResult}
   */

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
   * @param {Element | Node | HTMLElement} selectFrom - element to use for the querySelector call
   * @param {string} selector - the css selector to use
   * @returns {boolean}
   */
  function selectElemFromAndClick(selectFrom, selector) {
    return click(selectFrom.querySelector(selector));
  }

  addBehaviorStyle('.wr-debug-visited {border: 6px solid #3232F1;}');

  const xpQueries = {
    soundListItem:
      '//li[contains(@class, "soundsList__item") and not(contains(@class, "wrvistited"))]'
  };

  const selectors = {
    soundItem: 'div.soundItem',
    singleTrackEmbedPlay: 'button[role="application"].playButton'
  };

  function isMultiTrackEmbed(xpathGenerator) {
    return xpathGenerator(xpQueries.soundListItem).length > 0;
  }

  async function* playMultiTracks(xpathGenerator) {
    let snapShot = xpathGenerator(xpQueries.soundListItem);
    let soundItem;
    let i, len;
    if (snapShot.length === 0) return;
    do {
      len = snapShot.length;
      i = 0;
      for (; i < len; ++i) {
        soundItem = snapShot[i];
        soundItem.classList.add('wrvistited');
        await scrollIntoViewWithDelay(soundItem);
        yield selectElemFromAndClick(soundItem, selectors.soundItem);
      }
      snapShot = xpathGenerator(xpQueries.soundListItem);
      if (snapShot.length === 0) {
        await delay();
        snapShot = xpathGenerator(xpQueries.soundListItem);
      }
    } while (snapShot.length > 0);
  }

  async function* embedTrackIterator(xpathGenerator) {
    if (isMultiTrackEmbed(xpathGenerator)) {
      yield* playMultiTracks(xpathGenerator);
    } else {
      yield selectElemFromAndClick(document, selectors.singleTrackEmbedPlay);
    }
  }

  window.$WRIterator$ = embedTrackIterator(xpg);
  window.$WRIteratorHandler$ = async function() {
    const results = await $WRIterator$.next();
    return { done: results.done, wait: results.value };
  };
})($x, true);
