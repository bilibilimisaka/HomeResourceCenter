$(function() {
  $("input[name=title]").select();
  $("form.compose").submit(function() {
    var required = ["title", "markdown"];
    var form = $(this).get(0);
    for (var i = 0; i < required.length-1; i++) {
      if (!form[required[i]].value) {
        $(form[required[i]]).select();
        return false;
      }
    }
    return true;
  });
});