(function ($) {
  $(document).ready(function () {
    $('fieldset dl dd.basic').each(function() {
        var basic = $(this);
        var further = basic.next('.further');
        if (further.length) {
            var more = $('<span class="more">&nbsp;<span class="as_hyperlink">More &raquo;</span></span>');
            basic.append(more);
            further.hide();
            more.click(function(){
                further.slideDown('fast');
                $(this).hide()
            });
        };
    });
  })
})(jQuery);
