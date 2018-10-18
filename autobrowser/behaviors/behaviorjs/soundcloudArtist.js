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
  async function clickWithDelay(elem, delayTime = 1000) {
    let clicked = click(elem);
    if (clicked) {
      await delay(delayTime);
    }
    return clicked;
  }
  function selectElemFromAndClick(selectFrom, selector) {
    return click(selectFrom.querySelector(selector));
  }
  function selectElemFromAndClickWithDelay(
    selectFrom,
    selector,
    delayTime = 1000
  ) {
    return clickWithDelay(selectFrom.querySelector(selector), delayTime);
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
})($x);
