// ==UserScript==
// @id             ffn-dictionary
// @name           ffn-dictionary
// @version        2014.10.14
// @author         Chris Chu <cchu.tw@ffn.com>
// @description    Improvement template system
// @website        https://github.com/hiro0903/FFN/tree/master/template
// @updateURL      https://raw.github.com/hiro0903/FFN/master/template/assets/ffn-template.user.js
// @icon           https://raw.github.com/hiro0903/FFN/master/template/assets/favicon.png
// @grant          unsafeWindow
// @grant          GM_openInTab

// @include        *friendfinderinc.com*/cgi-bin/admin/dictionary/editor.cgi*

// @run-at         document-end
// ==/UserScript==

;(function(init){
  'use strict'
  var el_script = document.createElement('script')
  el_script.src = 'http://cdn.staticfile.org/seajs/2.1.1/sea.js'
  el_script.id = 'seajsnode'
  document.head.appendChild( el_script )

  unsafeWindow.FFN = { 
    open : GM_openInTab
  }

  el_script.onload = init
})(function(){
  unsafeWindow.seajs.use('https://rawgit.com/hiro0903/FFN/master/template/main.js')
})
