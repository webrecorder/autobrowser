(function runner(xpg, debug) {
  /**
   * @param {string} xpathQuery
   * @param {Element | Document} startElem
   * @return {XPathResult}
   */

  /**
   * @return {Promise<void>}
   */
  function domCompletePromise() {
    if (document.readyState !== 'complete') {
      return new Promise(r => {
        let i = setInterval(() => {
          if (document.readyState === 'complete') {
            clearInterval(i);
            r();
          }
        }, 1000);
      });
    }
    return Promise.resolve();
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

  function findAllMediaAndPlay() {
    const mediaElems = document.querySelectorAll('audio, video');
    let i = 0;
    for (; i < mediaElems.length; i++) {
      if (mediaElems[i].paused) {
        mediaElems[i].play();
      }
    }
  }

  const outlinks = new Set();
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

  Object.defineProperty(window, '$wbOutlinks$', {
    get() {
      return Array.from(outlinks);
    },
    set() {},
    enumerable: false
  });

  return domCompletePromise().then(() => {
    let scrollingTO = 2000;
    let lastScrolled = Date.now();
    let maxScroll = Math.max(
      document.body.scrollHeight,
      document.documentElement.scrollHeight
    );
    let scrollCount = 0;
    return new Promise((resolve, reject) => {
      let scrollerInterval = setInterval(() => {
        let scrollPos = window.scrollY + window.innerHeight;
        if (scrollCount < 50) {
          maxScroll = Math.max(
            document.body.scrollHeight,
            document.documentElement.scrollHeight
          );
          scrollCount += 1;
        }
        if (scrollPos < maxScroll) {
          window.scrollBy(0, 300);
          lastScrolled = Date.now();
        }
        collectOutlinksFrom(document);
        findAllMediaAndPlay();
        if (!lastScrolled || Date.now() - lastScrolled > scrollingTO) {
          if (scrollerInterval === undefined) {
            return;
          }
          clearInterval(scrollerInterval);
          scrollerInterval = undefined;
          resolve();
        } else if (scrollPos >= maxScroll) {
          clearInterval(scrollerInterval);
          scrollerInterval = undefined;
          resolve();
        }
      }, 500);
    });
  });
})($x, false);
