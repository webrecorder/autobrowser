// TODO(n0tan3rd): Expand comments and view them like twitter
// TODO(n0tan3rd): Need better scrolling here
(function viewNewsFeedSetup(xpg, debug = false) {
  if (document.getElementById('$wrStyle$') == null) {
    const style = document.createElement('style');
    style.id = '$wrStyle$';
    let sd = 'body, .wr-scroll-container { scroll-behavior: smooth }';
    if (debug) {
      sd += ' .wr-debug-visited {border: 6px solid #3232F1;}';
    }
    style.innerText = sd;
    document.head.appendChild(style);
  }
  
  const canScrollMore = () =>
    window.scrollY + window.innerHeight <
    Math.max(
      document.body.scrollHeight,
      document.body.offsetHeight,
      document.documentElement.clientHeight,
      document.documentElement.scrollHeight,
      document.documentElement.offsetHeight
    );
  
  const userTimelineSelector =
    '//div[contains(@class, "userContentWrapper") and not(contains(@class, "wrvistited"))]';
  
  const delay = (delayTime = 3000) => new Promise(r => setTimeout(r, delayTime));
  
  const moreReplies = 'a[role="button"].UFIPagerLink';
  const repliesToRepliesA = 'a[role="button"].UFICommentLink';
  const repliesToRepliesSpan = 'span.UFIReplySocialSentenceLinkText.UFIReplySocialSentenceVerified';
  
  
  function scrollIntoView(elem, delayTime = 2500) {
    elem.scrollIntoView({
      behavior: 'auto',
      block: 'center',
      inline: 'center'
    });
    return delay(delayTime);
  }
  
  function scrollDownByElemHeight(elem) {
    if (!elem) return;
    let rect = elem.getBoundingClientRect();
    window.scrollBy(0, rect.height + elem.offsetHeight);
  }
  
  function clickWithDelay(elem, delayTime = 2500) {
    elem.click();
    return delay(elem, delayTime)
  }
  
  async function scrollIntoViewAndClick(elem) {
    if (!elem) return;
    await scrollIntoView(elem);
    await clickWithDelay(elem);
  }

  async function* clickRepliesToReplies(tlItem) {
    let rToR = tlItem.querySelectorAll(repliesToRepliesA);
    let i = 0;
    let length = rToR.length;
    let rtr;
    while (i < length) {
      rtr = rToR[i];
      if (debug) rtr.classList.add('wr-debug-visited');
      await scrollIntoViewAndClick(rtr);
      yield rtr;
      i += 1;
    }
    rToR = tlItem.querySelectorAll(repliesToRepliesA);
    if (rToR.length) {
      i = 0;
      length = rToR.length;
      while (i < length) {
        rtr = rToR[i];
        if (debug) rtr.classList.add('wr-debug-visited');
        await scrollIntoViewAndClick(rtr);
        yield rToR;
        i += 1;
      }
    }
    await delay();
  }

  let removedBadElem = false;

  function maybeRemoveAnnoying() {
    const maybeAnnoying = document.getElementById('pagelet_growth_expanding_cta');
    if (maybeAnnoying) {
      maybeAnnoying.remove();
      removedBadElem = true;
    }
  }
  
  async function* timelineIterator(xpg) {
    let timelineItems = xpg(userTimelineSelector);
    let tlItem;
    let replies;
    do {
      while (timelineItems.length > 0) {
        tlItem = timelineItems.shift();
        if (window.$WRSTP$) return;
        if (debug) tlItem.classList.add('wr-debug-visited');
        await scrollIntoView(tlItem);
        tlItem.classList.add('wrvistited');
        yield tlItem;
        replies = tlItem.querySelector(moreReplies);
        if (replies) {
          if (debug) replies.classList.add('wr-debug-visited');
          await scrollIntoViewAndClick(replies);
          yield replies;
        }
        yield* clickRepliesToReplies(tlItem);
      }
      if (window.$WRSTP$) return;
      timelineItems = xpg(userTimelineSelector);
      if (timelineItems.length === 0) {
        scrollDownByElemHeight(tlItem);
        await delay();
        timelineItems = xpg(userTimelineSelector);
      }
      if (window.$WRSTP$) return;
    } while (timelineItems.length > 0 && canScrollMore());
  }

  window.$WRTLIterator$ = timelineIterator(xpg);
  window.$WRIteratorHandler$ = async function () {
    if (!removedBadElem) maybeRemoveAnnoying();
    const next = await $WRTLIterator$.next();
    return next.done;
  };

  maybeRemoveAnnoying();
  
})($x);
