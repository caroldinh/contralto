window.onload = function checkProgress(){
    console.log($("#progressBar").text());
    let pageUrl = window.location.href;
    pageUrl = pageUrl.split('/');
    let id = pageUrl[pageUrl.length - 1];

    //console.log(id);

    if($("#playist-name").text() == ""){
        $.ajax({
            url: "/" + id + "/info/",
            type: "get",
            success: function(response) {
                if(response.name != undefined){
                    $("#playlist-name").text("Playlist: " + response.name);
                }
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
            if(response != undefined && response != '0'){
                $("#progress-percent").text(parseInt(response * 100) + "%");
                $("#progress").css('width', (parseInt(response * 100)) + "%");
            }
            checkProgress();
        },
        error: function(xhr) {
            checkProgress();
        }
        });
    } else {
        $.ajax({
        url: "/analyzer-result/" + id,
        type: "get",
        success: function(response) {
            window.location.href=(id + '/result/')
        },
        error: function(xhr) {
            checkProgress();
        }
        });
    }
}