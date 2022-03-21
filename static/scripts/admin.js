artists_changed = {};

function changeVal(id){
    if(!(id in artists_changed)){
        artists_changed[id] = {};
    }
    artists_changed[id]['category'] = document.getElementById(id + "-select-category").value;
    console.log(artists_changed);
}

function lock(id){
    if(!(id in artists_changed)){
        artists_changed[id] = {};
    }
    if(document.getElementById("lock-" + id).innerText == "LOCK"){
        artists_changed[id]['locked'] = 1;
        document.getElementById("lock-" + id).innerText = "UNLOCK";
        document.getElementById("data-" + id).className = "artist-data data-locked";
    } else {
        artists_changed[id]['locked'] = 0;
        document.getElementById("lock-" + id).innerText = "LOCK";
        document.getElementById("data-" + id).className = "artist-data";
    }
    console.log(artists_changed);
}

function submit(){
    $.ajax({
    type: "POST",
    contentType: "application/json; charset=utf-8",
    url: "/",
    data: JSON.stringify(artists_changed),
    complete: function() {
        alert("Update successful");
        artists_changed = {};
        window.location.reload(true);
    },
    dataType: "json"
    });
}