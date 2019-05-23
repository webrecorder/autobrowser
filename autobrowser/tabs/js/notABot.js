(() => {
  // resist bot fingerprinting https://bot.sannysoft.com/
  if (navigator.webdriver) {
    try {
      const newProto = navigator.__proto__;
      delete newProto.webdriver;
      // eslint-disable-next-line
      navigator.__proto__ = newProto;
    } catch (e) {}
  }

  if (!window.outerWidth) {
    window.outerWidth = window.innerWidth;
  }

  if (!window.outerHeight) {
    window.outerHeight =
      window.innerHeight + Math.floor(Math.random() * 100) + 1;
  }

  if ((navigator.languages || []).length === 0) {
    const property = {};
    let handled = false;
    if (window.$$navigator$$languages$$) {
      try {
        const languages = window.$$navigator$$languages$$;
        property.get = () => languages;
        delete window.$$navigator$$languages$$;
        handled = true;
      } catch (e) {}
    }
    if (!handled) {
      property.get = () => ['en-US', 'en'];
    }
    try {
      Object.defineProperty(navigator, 'languages', property);
    } catch (e) {}
  }

  const dynamicToString = tsValue => {
    // ensure we always return the proper to toString.toString fn
    let cachedTs;
    return new Proxy(
      function toString() {
        return tsValue;
      },
      {
        get(target, prop) {
          if (prop === 'toString') {
            if (!cachedTs) cachedTs = dynamicToString(tsValue);
            return cachedTs;
          }
          return Reflect.get(target, prop);
        },
      }
    );
  };

  const addToString = (fn, fnsTs, fnName) => {
    if (!fn) return;
    fn.toString = function toString() {
      return fnsTs;
    };
    Object.defineProperty(fn.toString, 'toString', {
      value: dynamicToString('function toString() { [native code] }'),
    });
  };

  if (!window.chrome) {
    let csiv;
    const fakeChrome = {
      csi() {
        if (!csiv) {
          // idk on this one lets just make up things
          try {
            const navInfo = performance.getEntriesByType('navigation')[0];
            csiv = {
              onloadT: (
                performance.timeOrigin + navInfo.loadEventStart
              ).toFixed(),
              pageT: navInfo.domComplete,
              startE: (
                performance.timeOrigin + navInfo.domContentLoadedEventEnd
              ).toFixed(),
              tran: Math.floor(Math.random() * 30) + 1,
            };
          } catch (e) {
            const rands = crypto.getRandomValues(new Uint32Array(3));
            csiv = {
              onloadT: rands[0],
              pageT: rands[1] + Math.random(),
              startE: rands[2],
              tran: Math.floor(Math.random() * 98) + 1,
            };
          }
        }
        return csiv;
      },
      loadTimes() {
        // https://developers.google.com/web/updates/2017/12/chrome-loadtimes-deprecated
        const timeOrigin = performance.timeOrigin;
        const navInfo = performance.getEntriesByType('navigation')[0];
        const paint = performance.getEntriesByType('paint')[0];
        const h2Info = ['h2', 'hq', 'http/2+quic/43'].includes(
          navInfo.nextHopProtocol
        );
        let navtype;
        switch (navInfo.type) {
          case 'back_forward':
            navtype = 'BackForward';
            break;
          case 'link_clicked':
            navtype = 'LinkClicked';
            break;
          case 'form_submitted':
            navtype = 'FormSubmitted';
            break;
          case 'reload':
            navtype = 'Reload';
            break;
          case 'resubmitted':
            navtype = 'Resubmitted';
            break;
          default:
            navtype = 'Other';
            break;
        }
        return {
          commitLoadTime: (navInfo.responseStart + timeOrigin) / 1000,
          connectionInfo: navInfo.nextHopProtocol,
          finishDocumentLoadTime:
            (navInfo.domContentLoadedEventEnd + timeOrigin) / 1000,
          finishLoadTime: (navInfo.loadEventEnd + timeOrigin) / 1000,
          firstPaintAfterLoadTime: 0, // never impl
          firstPaintTime: ((paint ? paint.startTime : 0) + timeOrigin) / 1000,
          navigationType: navtype,
          npnNegotiatedProtocol: h2Info ? navInfo.nextHopProtocol : 'unknown',
          requestTime: (navInfo.startTime + timeOrigin) / 1000,
          startLoadTime: (navInfo.startTime + timeOrigin) / 1000,
          wasAlternateProtocolAvailable: false,
          wasFetchedViaSpdy: h2Info,
          wasNpnNegotiated: h2Info,
        };
      },
    };
    addToString(fakeChrome.csi, 'function () { [native code] }');
    addToString(fakeChrome.loadTimes, 'function () { [native code] }');
    window.chrome = fakeChrome;
  }

  if (!window.chrome.app) {
    const fakeApp = {
      isInstalled: false,
      InstallState: {
        DISABLED: 'disabled',
        INSTALLED: 'installed',
        NOT_INSTALLED: 'not_installed',
      },
      RunningState: {
        CANNOT_RUN: 'cannot_run',
        READY_TO_RUN: 'ready_to_run',
        RUNNING: 'running',
      },
      getDetails() {
        return null;
      },
      getIsInstalled() {
        return false;
      },
      installState(cb) {
        if (cb == null) {
          throw new TypeError(
            'Error in invocation of app.installState(function callback)'
          );
        }
        cb(['not_installed']);
      },
      runningState() {
        return 'cannot_run';
      },
    };

    addToString(fakeApp.getDetails, 'function getDetails() { [native code] }');
    addToString(
      fakeApp.installState,
      'function installState() { [native code] }'
    );
    addToString(
      fakeApp.getIsInstalled,
      'function getIsInstalled() { [native code] }'
    );
    addToString(
      fakeApp.runningState,
      'function runningState() { [native code] }'
    );
    window.chrome.app = fakeApp;
  }

  if (!window.chrome.runtime) {
    const runtime = {
      PlatformOs: {
        MAC: 'mac',
        WIN: 'win',
        ANDROID: 'android',
        CROS: 'cros',
        LINUX: 'linux',
        OPENBSD: 'openbsd',
      },
      PlatformArch: {
        ARM: 'arm',
        X86_32: 'x86-32',
        X86_64: 'x86-64',
        MIPS: 'mips',
        MIPS64: 'mips64',
      },
      PlatformNaclArch: {
        ARM: 'arm',
        X86_32: 'x86-32',
        X86_64: 'x86-64',
        MIPS: 'mips',
        MIPS64: 'mips64',
      },
      RequestUpdateCheckStatus: {
        THROTTLED: 'throttled',
        NO_UPDATE: 'no_update',
        UPDATE_AVAILABLE: 'update_available',
      },
      OnInstalledReason: {
        INSTALL: 'install',
        UPDATE: 'update',
        CHROME_UPDATE: 'chrome_update',
        SHARED_MODULE_UPDATE: 'shared_module_update',
      },
      OnRestartRequiredReason: {
        APP_UPDATE: 'app_update',
        OS_UPDATE: 'os_update',
        PERIODIC: 'periodic',
      },
      connect(id, info) {
        const sig =
          'runtime.connect(optional string extensionId, optional object connectInfo)';
        if (!id) {
          throw new TypeError(
            `Error in invocation of ${sig}: chrome.runtime.connect() called from a webpage must specify an Extension ID (string) for its first argument.`
          );
        }
        throw new TypeError(
          `Error in invocation of ${sig}: Invalid extension id: '${id}'`
        );
      },
      sendMessage(id, msg, opts) {
        const sig =
          'runtime.sendMessage(optional string extensionId, any message, optional object options, optional function responseCallback)';
        if (arguments.length === 0) {
          throw new TypeError(
            `Error in invocation of ${sig}: No matching signature`
          );
        }
        if (!id) {
          throw new TypeError(
            `Error in invocation of ${sig}: chrome.runtime.sendMessage() called from a webpage must specify an Extension ID (string) for its first argument`
          );
        }
        throw new TypeError(
          `Error in invocation of ${sig}: Invalid extension id: '${id}'`
        );
      },
    };
    addToString(runtime.connect, 'function connect() { [native code] }');
    addToString(
      runtime.sendMessage,
      'function sendMessage() { [native code] }'
    );
    window.chrome.runtime = runtime;
  }

  try {
    const canvas = document.createElement('canvas');
    const gl =
      canvas.getContext('webgl') || canvas.getContext('webgl-experimental');
    if (gl) {
      const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
      try {
        // WebGL Vendor Test
        const vendor = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL);
        const rendererWebGL = debugInfo.UNMASKED_RENDERER_WEBGL;
        const venderWebGL = debugInfo.UNMASKED_VENDOR_WEBGL;
        switch (vendor) {
          case 'Brian Paul':
          case 'Google Inc.':
            const oGetParam = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function getParameter(
              param
            ) {
              switch (param) {
                case rendererWebGL:
                  return 'Intel Open Source Technology Center';
                case venderWebGL:
                  return 'Mesa DRI Intel(R) UHD Graphics 630 (Coffeelake 3x8 GT2) ';
              }
              return oGetParam.call(this, param);
            };
            addToString(
              WebGLRenderingContext.prototype.getParameter,
              'function getParameter() { [native code] }'
            );
            break;
        }
      } catch (e) {}
    }
  } catch (e) {}

  if ((navigator.plugins || []).length === 0) {
    const pluginData = [
      {
        '0': {
          type: 'application/x-google-chrome-pdf',
          suffixes: 'pdf',
          description: 'Portable Document Format',
        },
        description: 'Portable Document Format',
        filename: 'internal-pdf-viewer',
        length: 1,
        name: 'Chrome PDF Plugin',
      },
      {
        '0': { type: 'application/pdf', suffixes: 'pdf', description: '' },
        description: '',
        filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
        length: 1,
        name: 'Chrome PDF Viewer',
      },
      {
        '0': {
          type: 'application/x-nacl',
          suffixes: '',
          description: 'Native Client Executable',
        },
        '1': {
          type: 'application/x-pnacl',
          suffixes: '',
          description: 'Portable Native Client Executable',
        },
        description: '',
        filename: 'internal-nacl-plugin',
        length: 2,
        name: 'Native Client',
      },
    ];

    class MimeType {
      constructor(mimeType, plugin) {
        const type = {
          get: function type() {
            return mimeType.type;
          },
          enumerable: false,
        };
        addToString(type.get, 'function get enabledPlugin() { [native code] }');
        Object.defineProperty(this, 'type', type);
        const suffixes = {
          get: function suffixes() {
            return mimeType.suffixes;
          },
          enumerable: false,
        };
        addToString(suffixes.get, 'function get suffixes() { [native code] }');
        Object.defineProperty(this, 'suffixes', suffixes);
        const description = {
          get: function description() {
            return mimeType.description;
          },
          enumerable: false,
        };
        addToString(
          description.get,
          'function get description() { [native code] }'
        );
        Object.defineProperty(this, 'description', description);
        const enabledPlugin = {
          get: function enabledPlugin() {
            return plugin;
          },
          enumerable: false,
        };
        addToString(
          enabledPlugin.get,
          'function get enabledPlugin() { [native code] }'
        );
        Object.defineProperty(this, 'enabledPlugin', enabledPlugin);
      }

      get [Symbol.toStringTag]() {
        return 'MimeType';
      }
    }

    addToString(
      MimeType.prototype.constructor,
      'function MimeType() { [native code] }'
    );

    class Plugin {
      constructor(plugin) {
        const description = {
          get: function description() {
            return plugin.description;
          },
          enumerable: false,
        };
        addToString(
          description.get,
          'function get description() { [native code] }'
        );
        Object.defineProperty(this, 'description', description);
        const filename = {
          get: function filename() {
            return plugin.filename;
          },
          enumerable: false,
        };
        addToString(filename.get, 'function get filename() { [native code] }');
        Object.defineProperty(this, 'filename', filename);
        const length = {
          get: function length() {
            return plugin.length;
          },
          enumerable: false,
        };
        addToString(length.get, 'function get length() { [native code] }');
        Object.defineProperty(this, 'length', length);
        const name = {
          get: function name() {
            return plugin.name;
          },
          enumerable: false,
        };
        addToString(name.get, 'function get name() { [native code] }');
        Object.defineProperty(this, 'name', name);
        for (let i = 0; i < plugin.length; i++) {
          const mt = new MimeType(plugin[i], this);
          this[i] = mt;
          Object.defineProperty(this, mt.type, {
            value: mt,
            enumerable: false,
          });
        }
      }

      item(idx) {
        return this[idx];
      }

      namedItem(name) {
        const item = this[name];
        if (!(item instanceof MimeType)) return undefined;
        return item;
      }

      get [Symbol.toStringTag]() {
        return 'Plugin';
      }

      [Symbol.iterator]() {
        const self = this;
        const iter = function*() {
          for (let i = 0; i < self.length; ++i) {
            yield self[i];
          }
        };
        return iter();
      }
    }

    addToString(
      Plugin.prototype.constructor,
      'function Plugin() { [native code] }'
    );
    addToString(Plugin.prototype.item, 'function item() { [native code] }');

    addToString(
      Plugin.prototype.namedItem,
      'function namedItem() { [native code] }'
    );

    addToString(
      Plugin.prototype[Symbol.iterator],
      'function values() { [native code] }'
    );

    class PluginArray {
      constructor(plugins) {
        for (let i = 0; i < plugins.length; i++) {
          const plugin = new Plugin(plugins[i]);
          this[i] = plugin;
          Object.defineProperty(this, plugin.name, {
            value: plugin,
            enumerable: false,
          });
        }

        Object.defineProperty(this, 'length', {
          get() {
            return plugins.length;
          },
          enumerable: false,
        });
      }

      refresh() {}

      item(idx) {
        return this[idx] || null;
      }

      namedItem(name) {
        const item = this[name];
        if (!(item instanceof Plugin)) return null;
        return item;
      }

      get [Symbol.toStringTag]() {
        return 'PluginArray';
      }

      [Symbol.iterator]() {
        const self = this;
        const iter = function*() {
          for (let i = 0; i < self.length; ++i) {
            yield self[i];
          }
        };
        return iter();
      }
    }

    addToString(
      PluginArray.prototype.constructor,
      'function PluginArray() { [native code] }'
    );

    addToString(
      PluginArray.prototype.item,
      'function item() { [native code] }'
    );

    addToString(
      PluginArray.prototype.refresh,
      'function refresh() { [native code] }'
    );

    addToString(
      PluginArray.prototype.namedItem,
      'function namedItem() { [native code] }'
    );

    addToString(
      PluginArray.prototype[Symbol.iterator],
      'function values() { [native code] }'
    );

    const plugins_ = new PluginArray(pluginData);
    window.PluginArray = PluginArray;
    window.Plugin = Plugin;
    window.MimeType = MimeType;
    const pluginsPD = {
      get: function plugins() {
        return plugins_;
      },
    };
    addToString(pluginsPD.get, 'function get plugins() { [native code] }');
    Object.defineProperty(navigator, 'plugins', pluginsPD);

    class MimeTypeArray {
      constructor(plugins) {
        let length = 0;
        for (let i = 0; i < plugins.length; i++) {
          let plugin = plugins[i];
          for (let j = 0; j < plugin.length; j++) {
            const mimeType = plugin[j];
            this[length] = mimeType;
            length += 1;
            Object.defineProperty(this, mimeType.type, {
              value: mimeType,
              enumerable: false,
            });
          }
        }

        Object.defineProperty(this, 'length', {
          get() {
            return length;
          },
          enumerable: false,
        });
      }

      item(idx) {
        return this[idx] || null;
      }

      namedItem(name) {
        const item = this[name];
        if (!(item instanceof MimeType)) return null;
        return item;
      }

      get [Symbol.toStringTag]() {
        return 'MimeTypeArray';
      }

      [Symbol.iterator]() {
        const self = this;
        const iter = function*() {
          for (let i = 0; i < self.length; ++i) {
            yield self[i];
          }
        };
        return iter();
      }
    }

    addToString(
      MimeTypeArray.prototype.constructor,
      'function MimeTypeArray() { [native code] }'
    );

    addToString(
      MimeTypeArray.prototype.item,
      'function item() { [native code] }'
    );

    addToString(
      MimeTypeArray.prototype.namedItem,
      'function namedItem() { [native code] }'
    );

    addToString(
      MimeTypeArray.prototype[Symbol.iterator],
      'function values() { [native code] }'
    );

    const mimeTypes_ = new MimeTypeArray(plugins_);
    const mimeTypesPD = {
      get: function mimeTypes() {
        return mimeTypes_;
      },
    };
    addToString(mimeTypesPD.get, 'function get mimeTypes() { [native code] }');
    Object.defineProperty(navigator, 'mimeTypes', mimeTypesPD);

    window.MimeTypeArray = MimeTypeArray;
  }
})();
