window.onload = function checkProgress(){
    console.log($("#progressBar").text());
    let pageUrl = window.location.href;
    pageUrl = pageUrl.split('/');
    let id = pageUrl[pageUrl.length - 1];

    if($("#playist-name").text() == ""){
        $.ajax({
            url: "/" + id + "/info/",
            type: "get",
            success: function(response) {
                $("#playlist-name").text("Playlist: " + response.name);
            },
            error: function(xhr) {
                //Do Something to handle error
            }
            });
    }

    if($("#progress-percent").text() != "100%"){
        $.ajax({
        url: "/analyzer-progress/" + id,
        type: "get",
        success: function(response) {
            $("#progress-percent").text(parseInt(response * 100) + "%");
            $("#progress").css('width', (parseInt(response * 100)) + "%");
            checkProgress();
        },
        error: function(xhr) {
            //Do Something to handle error
        }
        });
    } else {
        $.ajax({
        url: "/analyzer-result/" + id,
        type: "get",
        success: function(response) {
            $("#progress-percent").text(parseInt(response * 100) + "%");
            $("#progress").css('width', (parseInt(response * 100)) + "%");
            window.location.href=(id + '/result/')
        },
        error: function(xhr) {
            //Do Something to handle error
        }
        });
    }
}