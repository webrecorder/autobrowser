(async function consumeTweets(xpg) {
  class TweetStream {
    constructor(xpathGenerator) {
      this.tweetXpath = '//div[starts-with(@class,"tweet js-stream-tweet")]/div[@class="content"]';
      this._stopped = false;
      this.xpathGenerator = xpathGenerator;
      this.currentTweets = [];
    }

    start() {
      this._stopped = true;
    }

    stop() {
      this._stopped = true;
    }

    _getTweets() {
      return this.xpathGenerator(this.tweetXpath);
    }

    * _stream() {
      this.currentTweets = this.currentTweets.concat(this._getTweets());
      let aTweet;
      do {
        while (this.currentTweets.length && !this._stopped) {
          aTweet = this.currentTweets.shift();
          aTweet.classList.add('$wrvistited$');
          aTweet.scrollIntoView(true);
          yield aTweet;
        }
        this.currentTweets = this.currentTweets.concat(this._getTweets());
      } while (!this._stopped && this.currentTweets.length > 0);
    }

    [Symbol.iterator]() {
      this._stopped = false;
      return this._stream();
    }
  }

  let ts = new TweetStream(xpg);
  let aTweet;
  do {
    for (aTweet of ts) {
      console.log(aTweet);
    }
    await new Promise(r => setTimeout(r, 3000));
  } while (window.scrollY + window.innerHeight < Math.max(document.body.scrollHeight, document.documentElement.scrollHeight));
})($x);
