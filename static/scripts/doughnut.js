window.onload = function displayChart(){
    let pageUrl = window.location.href;
    pageUrl = pageUrl.split('/');
    let id = pageUrl[pageUrl.length - 3];
    $.ajax({
        url: "/" + id + "/artists/",
        type: "get",
        success: function(response) {
            let tracks_male = 0;
            const maleArtists = document.getElementById("male-artists").getElementsByClassName("artists-list")[0];
            Object.values(response.male).forEach(function(element){
                let artist = document.createElement("span");
                artist.className = "male-artist";
                artist.innerText=element.name;
                tracks_male += element.occurrences;
                maleArtists.appendChild(artist);
            });

            let tracks_underrep = 0;
            const underrepArtists = document.getElementById("underrep-artists").getElementsByClassName("artists-list")[0];
            Object.values(response.female).forEach(function(element){
                let artist = document.createElement("span");
                artist.className = "underrep-artist";
                artist.innerText=element.name;
                tracks_underrep += element.occurrences;
                underrepArtists.appendChild(artist);
            });
            Object.values(response.nonbinary).forEach(function(element){
                let artist = document.createElement("span");
                artist.className = "underrep-artist";
                artist.innerText=element.name;
                tracks_underrep += element.occurrences;
                underrepArtists.appendChild(artist);
            });
            
            let tracks_mixed = 0;
            const mixedGender = document.getElementById("mixed-gender").getElementsByClassName("artists-list")[0];
            Object.values(response.mixed_gender).forEach(function(element){
                let artist = document.createElement("span");
                artist.className = "mixed-group";
                artist.innerText=element.name;
                tracks_mixed += element.occurrences;
                mixedGender.appendChild(artist);
            });

            let tracks_undetermined = 0;
            const undeterminedArtists = document.getElementById("undetermined-artists");
            let count = 0;
            Object.values(response.undetermined).forEach(function(element){
                let artist = document.createElement("span");
                tracks_undetermined += element.occurrences;
                if(count == Object.values(response.undetermined).length - 1){
                    artist.innerText=element.name;
                } else {
                    artist.innerText=element.name + ", ";
                }
                undeterminedArtists.appendChild(artist);
                count++;
            });

            const ctx = $("#artists-chart");
            const data = {
                labels: [
                    'Men',
                    'Women & nonbinary',
                    'Mixed-gender bands',
                    'Undetermined'
                ],
                datasets: [{
                    label: 'Artist Data',
                    data: [tracks_male, tracks_underrep, tracks_mixed, tracks_undetermined],
                    backgroundColor: [
                        '#71B2EB',
                        '#E77849',
                        '#D287D8',
                        '#F0BDD0'
                    ],
                    hoverBackgroundColor: [
                        '#71B2EB',
                        '#E77849',
                        '#D287D8',
                        '#F0BDD0'
                    ],
                    borderWidth: 10,
                    hoverOffset: 4
                    }]
                };
                const config = {
                    type: 'doughnut',
                    data: data,
                    options: {
                    plugins: {
                        legend: {
                            display: false,
                        }
                    }
                }
            };

            const myChart = new Chart(ctx, config);

        },
        error: function(xhr) {
            //Do Something to handle error
        }
    });
}