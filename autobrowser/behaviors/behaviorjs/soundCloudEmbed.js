(function runner(xpg, debug = false) {
  function delay(delayTime = 3000) {
    return new Promise(resolve => {
      setTimeout(resolve, delayTime);
    });
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
  function selectElemFromAndClick(selectFrom, selector) {
    return click(selectFrom.querySelector(selector));
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
})($x);
