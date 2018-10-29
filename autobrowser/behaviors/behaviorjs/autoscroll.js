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

  class OutLinkCollector {
    constructor() {
      /**
       * @type {Set<string>}
       */
      this.outlinks = new Set();
      this.ignored = [
        'about:',
        'data:',
        'mailto:',
        'javascript:',
        'js:',
        '{',
        '*',
        'ftp:',
        'tel:'
      ];
      this.good = { 'http:': true, 'https:': true };
      this.urlParer = new URL('about:blank');
      this.outlinkSelector = 'a[href], area[href]';
    }

    shouldIgnore(test) {
      let ignored = false;
      let i = this.ignored.length;
      while (i--) {
        if (test.startsWith(this.ignored[i])) {
          ignored = true;
          break;
        }
      }
      if (!ignored) {
        let parsed = true;
        try {
          this.urlParer.href = test;
        } catch (error) {
          parsed = false;
        }
        return !(parsed && this.good[this.urlParer.protocol]);
      }
      return ignored;
    }

    collectFromDoc() {
      this.addOutLinks(document.querySelectorAll(this.outlinkSelector));
    }

    collectFrom(queryFrom) {
      this.addOutLinks(queryFrom.querySelectorAll(this.outlinkSelector));
    }

    addOutLinks(outlinks) {
      let href;
      let i = outlinks.length;
      while (i--) {
        href = outlinks[i].href.trim();
        if (href && !this.outlinks.has(href) && !this.shouldIgnore(href)) {
          this.outlinks.add(href);
        }
      }
    }

    /**
     * @param {HTMLAnchorElement|HTMLAreaElement|string} elemOrString
     */
    addOutlink(elemOrString) {
      const href = (elemOrString.href || elemOrString).trim();
      if (href && !this.outlinks.has(href) && !this.shouldIgnore(href)) {
        this.outlinks.add(href);
      }
    }

    /**
     * @return {string[]}
     */
    outLinkArray() {
      return Array.from(this.outlinks);
    }

    /**
     * @return {string[]}
     */
    toJSON() {
      return this.outLinkArray();
    }

    /**
     * @return {string[]}
     */
    valueOf() {
      return this.outLinkArray();
    }
  }

  const OLC = new OutLinkCollector();

  Object.defineProperty(window, '$wbOutlinks$', {
    value: OLC,
    writable: false,
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
        OLC.collectFromDoc();
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
