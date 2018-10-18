(function runner(xpg, debug = false) {
  function delay(delayTime = 3000) {
    return new Promise(resolve => {
      setTimeout(resolve, delayTime);
    });
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

  function xpathSnapShot(xpathQuery, startElem) {
    if (startElem == null) {
      startElem = document;
    }
    return document.evaluate(
      xpathQuery,
      startElem,
      null,
      XPathResult.ORDERED_NODE_SNAPSHOT_TYPE,
      null
    );
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
  function canScrollMore() {
    return (
      window.scrollY + window.innerHeight <
      Math.max(
        document.body.scrollHeight,
        document.body.offsetHeight,
        document.documentElement.clientHeight,
        document.documentElement.scrollHeight,
        document.documentElement.offsetHeight
      )
    );
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
  async function clickAndWaitFor(elem, predicate) {
    const clicked = click(elem);
    if (clicked) {
      await waitForPredicate(predicate);
    }
    return clicked;
  }

  addBehaviorStyle(
    '.wr-debug-visited {border: 6px solid #3232F1;} .wr-debug-visited-thread-reply {border: 6px solid green;} .wr-debug-visited-overlay {border: 6px solid pink;} .wr-debug-click {border: 6px solid red;}'
  );
  const tweetFooterSelector = 'div.stream-item-footer';
  const replyActionSelector = 'div.ProfileTweet-action--reply';
  const noReplySpanSelector = 'span.ProfileTweet-actionCount--isZero';
  const replyBtnSelector = 'button[data-modal="ProfileTweet-reply"]';
  const closeFullTweetSelector = 'div.PermalinkProfile-dismiss > span';
  const threadSelector = 'a.js-nav.show-thread-link';
  const tweetXpath =
    '//div[starts-with(@class,"tweet js-stream-tweet")]/div[@class="content"]';
  const overlayTweetXpath = `//div[@id="permalink-overlay"]${tweetXpath}`;
  class Tweet {
    constructor(aTweet, baseURI) {
      markElemAsVisited(aTweet);
      this.tweet = aTweet;
      this.container = aTweet.parentElement;
      this.dataset = this.container.dataset;
      this.footer = this.tweet.querySelector(tweetFooterSelector);
      this.tRplyAct = this.footer.querySelector(replyActionSelector);
      this.rplyButton = this.tRplyAct.querySelector(replyBtnSelector);
      this.fullTweetOverlay = null;
      this._hasReplys =
        this.rplyButton.querySelector(noReplySpanSelector) == null;
      this._apartThread = this.tweet.querySelector(threadSelector) != null;
      this._baseURI = baseURI;
    }
    tweetId() {
      return this.dataset.tweetId;
    }
    permalinkPath() {
      return this.dataset.permalinkPath;
    }
    hasReplys() {
      return this._hasReplys;
    }
    apartOfThread() {
      return this._apartThread;
    }
    hasRepliedOrInThread() {
      return this.hasReplys() || this.apartOfThread();
    }
    async *viewRepliesOrThread() {
      await this.openFullTweet();
      yield* this.visitThreadReplyTweets();
      await this.closeFullTweetOverlay();
    }
    async *viewRegularTweet() {
      await this.openFullTweet();
      yield this.fullTweetOverlay;
      await this.closeFullTweetOverlay();
    }
    openFullTweet() {
      const permalinkPath = this.permalinkPath();
      return clickAndWaitFor(this.container, () => {
        const done = document.baseURI.endsWith(permalinkPath);
        if (done) {
          this.fullTweetOverlay = document.getElementById('permalink-overlay');
          if (debug) {
            this.fullTweetOverlay.classList.add('wr-debug-visited-overlay');
          }
        }
        return done;
      });
    }
    async *visitThreadReplyTweets() {
      let snapShot = xpathSnapShot(overlayTweetXpath, this.fullTweetOverlay);
      let aTweet;
      let i, len;
      if (snapShot.snapshotLength === 0) return;
      do {
        len = snapShot.snapshotLength;
        i = 0;
        while (i < len) {
          aTweet = snapShot.snapshotItem(i);
          markElemAsVisited(aTweet);
          if (debug) {
            aTweet.classList.add('wr-debug-visited-thread-reply');
          }
          await scrollIntoViewWithDelay(aTweet, 500);
          yield aTweet;
          i += 1;
        }
        snapShot = xpathSnapShot(overlayTweetXpath, this.fullTweetOverlay);
        if (snapShot.snapshotLength === 0) {
          if (
            selectElemFromAndClick(
              this.fullTweetOverlay,
              'button.ThreadedConversation-showMoreThreadsButton'
            )
          ) {
            await delay();
          }
          snapShot = xpathSnapShot(overlayTweetXpath, this.fullTweetOverlay);
        }
      } while (snapShot.snapshotLength > 0);
    }
    closeFullTweetOverlay() {
      const overlay = document.querySelector(closeFullTweetSelector);
      if (!overlay) return Promise.resolve(false);
      if (debug) overlay.classList.add('wr-debug-click');
      return clickAndWaitFor(overlay, () => {
        const done = document.baseURI === this._baseURI;
        if (done && debug) {
          overlay.classList.remove('wr-debug-click');
        }
        return done;
      });
    }
  }
  async function* timelineIterator(xpathQuerySelector, baseURI) {
    let tweets = xpathQuerySelector(tweetXpath);
    let aTweet;
    do {
      while (tweets.length > 0) {
        aTweet = new Tweet(tweets.shift(), baseURI);
        if (debug) {
          aTweet.tweet.classList.add('wr-debug-visited');
        }
        await scrollIntoViewWithDelay(aTweet.tweet, 500);
        yield aTweet.tweet;
        if (aTweet.hasRepliedOrInThread()) {
          yield* aTweet.viewRepliesOrThread();
        } else {
          yield* aTweet.viewRegularTweet();
        }
      }
      tweets = xpathQuerySelector(tweetXpath);
      if (tweets.length === 0) {
        await delay();
        tweets = xpathQuerySelector(tweetXpath);
      }
    } while (tweets.length > 0 && canScrollMore());
  }
  window.$WRTweetIterator$ = timelineIterator(
    maybePolyfillXPG(xpg),
    document.baseURI
  );
  window.$WRIteratorHandler$ = async function() {
    const next = await $WRTweetIterator$.next();
    return next.done;
  };
})($x);
