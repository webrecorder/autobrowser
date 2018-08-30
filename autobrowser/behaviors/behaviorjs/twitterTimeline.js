(async function consumeTweets(xpg) {
  if (xpg.toString().indexOf("[Command Line API]") === -1) {
    /**
     * @desc Polyfill console api $x
     * @param {string} xpathQuery
     * @return {Array<HTMLElement>}
     */
    xpg = function(xpathQuery) {
      const snapShot = document.evaluate(
        xpathQuery,
        document,
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

  /**
   * @desc An abstraction around interacting with HTML of a tweet in a timeline.
   *
   *  Selector, element breakdown:
   *    div.tweet.js-stream-tweet... (_container)
   *     |- div.content (aTweet, _tweet)
   *         |- div.stream-item-footer (_footer)
   *             |- div.ProfileTweet-action--reply (_tRplyAct)
   *                 |- button[data-modal="ProfileTweet-reply"] (_rplyButton)
   *                     |- span.ProfileTweet-actionCount--isZero (IFF no replies)
   *    |- div.self-thread-tweet-cta
   *        |- a.js-nav.show-thread-link
   */
  class Tweet {
    /**
     *
     * @param {HTMLElement} aTweet - The content div for a tweet in a timeline
     * @param {string} baseURI - The document.baseURI of the timeline page being viewed
     */
    constructor(aTweet, baseURI) {
      this.tweetFooterSelector = "div.stream-item-footer";
      this.replyActionSelector = "div.ProfileTweet-action--reply";
      this.noReplySpanSelector = "span.ProfileTweet-actionCount--isZero";
      this.replyBtnSelector = 'button[data-modal="ProfileTweet-reply"]';
      this.closeFullTweetSelector = "div.PermalinkProfile-dismiss > span";
      this._tweet = aTweet;
      this._container = aTweet.parentElement;
      this._dataset = this._container.dataset;
      this._footer = this._tweet.querySelector(this.tweetFooterSelector);
      this._tRplyAct = this._footer.querySelector(this.replyActionSelector);
      this._rplyButton = this._tRplyAct.querySelector(this.replyBtnSelector);

      /**
       * @desc If the currently visited tweet has replies then the span with
       * class `ProfileTweet-actionCount--isZero` must not exist
       * @type {boolean}
       * @private
       */
      this._hasReplys =
        this._rplyButton.querySelector(this.noReplySpanSelector) == null;

      /**
       * @desc If the currently visited tweet is apart of a thread,
       * then an a tag will be present with classes `js-nav.show-thread-link`
       * @type {boolean}
       * @private
       */
      this._apartThread =
        this._tweet.querySelector("a.js-nav.show-thread-link") != null;
      this._baseURI = baseURI;
    }

    tweetId() {
      return this._dataset.tweetId;
    }

    permalinkPath() {
      return this._dataset.permalinkPath;
    }

    hasReplys() {
      return this._hasReplys;
    }

    apartOfThread() {
      return this._apartThread;
    }

    /**
     * @desc Clicks (views) the currently visited tweet
     * @return {Promise<void>}
     */
    viewFullTweet() {
      this._container.click();
      const permalinkPath = this.permalinkPath();
      return new Promise(resolve => {
        let interval = setInterval(() => {
          if (document.baseURI.endsWith(permalinkPath)) {
            clearInterval(interval);
            resolve();
          }
        }, 1500);
      });
    }

    /**
     * @desc Closes the overlay representing viewing a tweet
     * @return {Promise<void>}
     */
    closeFullTweetOverlay() {
      const overlay = document.querySelector(this.closeFullTweetSelector);
      if (!overlay) return Promise.resolve();
      return new Promise((resolve, reject) => {
        overlay.click();
        let ninterval = setInterval(() => {
          if (document.baseURI === this._baseURI) {
            clearInterval(ninterval);
            resolve();
          }
        }, 1500);
      });
    }
  }

  /**
   * @desc Xpath query used to traverse each tweet within a timeline.
   *
   * Because {@link timelineTraversalIterator} marks each tweet as visited by adding the
   * sentinel`$wrvisited$` to the classList of a tweet seen during timeline traversal,
   * normal usage of a CSS selector and `document.querySelectorAll` is impossible
   * unless significant effort is made in order to ensure each tweet is seen only
   * once during timeline traversal.
   *
   * Tweets in a timeline have the following structure:
   *  div.tweet.js-stream-tweet.js-actionable-tweet.js-profile-popup-actionable.dismissible-content...
   *    |- div.content
   *       |- ...
   *  div.tweet.js-stream-tweet.js-actionable-tweet.js-profile-popup-actionable.dismissible-content...
   *   |- div.content
   *      |- ...
   *
   * We care only about the minimal identifiable markers of a tweet:
   *  div.tweet.js-stream-tweet...
   *   |- div.content
   *
   * such that when a tweet is visited during timeline traversal it becomes:
   *  div.tweet.js-stream-tweet...
   *   |- div.content.$wrvistited$
   *
   * which invalidates the query on subsequent evaluations against the DOM,
   * thus allowing for unique traversal of each tweet in a timeline.
   * @type {string}
   */
  const tweetXpath =
    '//div[starts-with(@class,"tweet js-stream-tweet")]/div[@class="content"]';

  /**
   * @desc Determines if we can scroll the timeline any more
   * @return {boolean}
   */
  const canScrollMore = () =>
    window.scrollY + window.innerHeight <
    Math.max(document.body.scrollHeight, document.documentElement.scrollHeight);

  /**
   * @desc For a more detailed explanation about the relationship between the xpath
   * query used and the marking of each tweet as visited by this algorithm see the
   * description for {@link tweetXpath}.
   *
   * (S1) Build initial set of to be visited tweets
   * (S2) For each tweet visible at current scroll position:
   *      - mark as visited
   *      - scroll into view
   *      - yield tweet
   * (S3) Once all tweets at current scroll position have been visited:
   *      - wait for Twitter to load more tweets (if more are to be had)
   *      - if twitter added more tweets, add them to the to be visited set
   * (S4) If we have more tweets to visit and can scroll more:
   *      - GOTO S2
   *
   * @param {function(string): Array<HTMLElement>} xpathQuerySelector
   * @param {string} baseURI - The timelines documents baseURI
   * @return {AsyncIterator<Tweet>}
   */
  async function* timelineTraversalIterator(xpathQuerySelector, baseURI) {
    let tweets = xpathQuerySelector(tweetXpath);
    let aTweet;
    do {
      while (tweets.length > 0) {
        aTweet = tweets.shift();
        aTweet.classList.add("$wrvistited$");
        aTweet.scrollIntoView(true, { behavior: "smooth" });
        yield new Tweet(aTweet, baseURI);
      }
      await new Promise(r => setTimeout(r, 3000));
      tweets = tweets.concat(xpathQuerySelector(tweetXpath));
    } while (tweets.length > 0 && canScrollMore());
  }

  let aTweet;
  let tweetIterator = timelineTraversalIterator(xpg, document.baseURI);
  for await (aTweet of tweetIterator) {
    if (aTweet.hasReplys() || aTweet.apartOfThread()) {
      await aTweet.viewFullTweet();
      await aTweet.closeFullTweetOverlay();
    }
  }
})($x);
