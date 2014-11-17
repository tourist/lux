    //
    //  Lux Static JSON API
    //  ------------------------
    //
    //  Api used by static sites
    angular.module('lux.static.api', ['lux.api'])

        .run(['$lux', function ($lux) {
            var pageCache = {};

            $lux.registerApi('static', {
                //
                url: function (urlparams) {
                    var url = this._url,
                        name = urlparams ? urlparams.slug : null;
                    if (url.substring(url.length-5) === '.json')
                        return url;
                    if (url.substring(url.length-1) !== '/')
                        url += '/';
                    url += name || 'index';
                    if (url.substring(url.length-5) === '.html')
                        url = url.substring(0, url.length-5);
                    else if (url.substring(url.length-1) === '/')
                        url += 'index';
                    if (url.substring(url.length-5) !== '.json')
                        url += '.json';
                    return url;
                },
                //
                getPage: function (page, state, stateParams) {
                    var href = lux.stateHref(state, page.name, stateParams),
                        data = pageCache[href];
                    if (data)
                        return data;
                    //
                    return this.get(stateParams).success(function (data) {
                        pageCache[href] = data;
                        forEach(data.require_css, function (css) {
                            loadCss(css);
                        });
                        if (data.require_js) {
                            var defer = $lux.q.defer();
                            require(rcfg.min(data.require_js), function () {
                                defer.resolve(data);
                            });
                            return defer.promise;
                        } else
                            return data;
                    });
                },
                //
                getItems: function (page, state, stateParams) {
                    if (page.apiItems)
                        return this.getList();
                }
            });
        }]);
