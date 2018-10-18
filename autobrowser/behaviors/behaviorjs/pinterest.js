(function runner(xpg, debug = false) {
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
  function addBehaviorStyle(styleDef) {
    if (document.getElementById('$wrStyle$') == null) {
      const style = document.createElement('style');
      style.id = '$wrStyle$';
      style.textContent = styleDef;
      document.head.appendChild(style);
    }
  }

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

  let reactProps = {
    rootContainer: '_reactRootContainer',
    internalRoot: '_internalRoot',
    onDomNode: '__reactInternalInstance',
    rootHostElemId: 'react-root',
    mProps: 'memoizedProps'
  };
  function reactInstanceFromDOMElem(elem) {
    const keys = Object.keys(elem);
    let i = 0;
    let len = keys.length;
    let internalKey;
    for (; i < len; ++i) {
      if (keys[i].startsWith(reactProps.onDomNode)) {
        internalKey = keys[i];
        break;
      }
    }
    if (!internalKey) throw new Error('Could not find react internal key');
    return elem[internalKey];
  }
  function reactInstancesFromElements(elems, selectingFn) {
    const renderedNodes = [];
    const length = elems.length;
    let i = 0;
    let node;
    let reactInstance;
    for (; i < length; ++i) {
      node = elems[i];
      reactInstance = reactInstanceFromDOMElem(node);
      if (selectingFn(reactInstance.key)) {
        renderedNodes.push({ node, reactInstance });
      }
    }
    return renderedNodes;
  }

  addBehaviorStyle('.wr-debug-visited {border: 6px solid #3232F1;}');
  async function* consumePins(renderedPins) {
    let pin;
    let i = 0;
    let numPins = renderedPins.length;
    for (; i < numPins; ++i) {
      pin = renderedPins[i];
      await scrollIntoViewWithDelay(pin.node);
      yield pin.node;
    }
  }
  const selectors = {
    gridImage: 'div[data-grid-item]',
    gridContainer: 'div.gridCentered > div > div > div'
  };
  function getGridContainer() {
    const firstChild = document.querySelector(selectors.gridImage);
    const container = firstChild.parentElement;
    if (container !== document.querySelector(selectors.gridContainer)) {
      throw new Error('wrong container');
    }
    return container;
  }
  async function* iteratePins(xpathGenerator) {
    const seenPins = new Set();
    const pinContainerR = reactInstanceFromDOMElem(getGridContainer());
    const getRenderedPins = () =>
      reactInstancesFromElements(pinContainerR.stateNode.childNodes, key => {
        const select = !seenPins.has(key);
        if (select) {
          seenPins.add(key);
        }
        return select;
      });
    let currentPostRows = getRenderedPins();
    do {
      yield* consumePins(currentPostRows);
      currentPostRows = getRenderedPins();
    } while (currentPostRows.length > 0);
    if (currentPostRows.length === 0) {
      currentPostRows = getRenderedPins();
    }
    do {
      yield* consumePins(currentPostRows);
      currentPostRows = getRenderedPins();
    } while (currentPostRows.length > 0);
  }
  window.$WRIterator$ = iteratePins(maybePolyfillXPG(xpg));
  window.$WRIteratorHandler$ = async function() {
    const next = await $WRIterator$.next();
    return next.done;
  };
})($x);
