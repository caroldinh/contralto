
artists_changed = {};
artists_voted = {};
let playlistId;

window.onload = function getID(){
    localStorage.clear();
    let pageUrl = window.location.href;
    pageUrl = pageUrl.split('/');
    playlistId = pageUrl[pageUrl.length - 3];
    artists_voted = localStorage.getItem('contralto-artists-voted');
    console.log("Artists voted: ");
    console.log(artists_voted);
    if(artists_voted == null){
        artists_voted = {};
    } else {
        artists_voted = JSON.parse(artists_voted);
        let today = new Date();
        let temp_artists_voted = artists_voted;
        Object.keys(temp_artists_voted).forEach(date => {
            let date_list = date.split('-');
            let year = parseInt(date_list[0]);
            let month = parseInt(date_list[1]);
            let day = parseInt(date_list[2]);
            if(today.getFullYear() != year || today.getMonth() != (month - 1) || today.getDate() != day){
                delete artists_voted[date];
            } else {
                console.log("Don't delete");
                artists_voted[date].forEach(id => {
                    console.log(id);
                    artist_div = document.getElementById(id + "-div");
                    artist_div.remove();
                });
            }
        });
        console.log("New artists_voted");
        console.log(artists_voted);
    }
}

function changeVal(id){
    if(!(id in artists_changed)){
        artists_changed[id] = {};
    }
    artists_changed[id]['category'] = document.getElementById(id + "-select-category").value;
    console.log(artists_changed);
}

window.onbeforeunload = function() {
    if(artists_changed.length > 0){
        let save = confirm("Save changes before leaving?");
        if(save){
            submit();
        } else {
            return;
        }
    }
};

function submit(){
    $.ajax({
    type: "POST",
    contentType: "application/json; charset=utf-8",
    url: "/" + playlistId + "/check-us/",
    data: JSON.stringify(artists_changed),
    dataType: 'text',
    complete: function() {
        let today = new Date();
        let date = today.getFullYear()+'-'+(today.getMonth() + 1)+'-'+today.getDate();
        if(artists_voted[date] == undefined){
            artists_voted[date] = [];
        }
        Object.keys(artists_changed).forEach(id => {
            artists_voted[date].push(id);
            console.log(id);
        });
        localStorage.setItem('contralto-artists-voted', JSON.stringify(artists_voted));
        console.log(artists_voted);
        artists_changed = {};
        window.location.href='/' + (playlistId) + '/result/';
    },
    dataType: "json"
    });
}