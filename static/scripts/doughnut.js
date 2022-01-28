window.onload = function displayChart(){
    let pageUrl = window.location.href;
    pageUrl = pageUrl.split('/');
    let id = pageUrl[pageUrl.length - 3];
    $.ajax({
        url: "/" + id + "/artists/",
        type: "get",
        success: function(response) {
            const ctx = $("#artists-chart");
            let male_led = Object.keys(response.male_led).length;
            let underrepresented = Object.keys(response.underrepresented).length;
            let mixed_gender = Object.keys(response.mixed_gender).length;
            let undetermined = Object.keys(response.undetermined).length;
            const data = {
                labels: [
                    'Male artists',
                    'Female or nonbinary artists',
                    'Mixed-gender bands',
                    'Undetermined'
                ],
                datasets: [{
                    label: 'Artist Data',
                    data: [male_led, underrepresented, mixed_gender, undetermined],
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

            const maleArtists = document.getElementById("male-artists").getElementsByClassName("artists-list")[0];
            Object.values(response.male_led).forEach(function(element){
                let artist = document.createElement("span");
                artist.className = "male-artist";
                artist.innerText=element;
                maleArtists.appendChild(artist);
            });

            const underrepArtists = document.getElementById("underrep-artists").getElementsByClassName("artists-list")[0];
            Object.values(response.underrepresented).forEach(function(element){
                let artist = document.createElement("span");
                artist.className = "underrep-artist";
                artist.innerText=element;
                underrepArtists.appendChild(artist);
            });

            const mixedGenderGroups = document.getElementById("undetermined-artists");
            let count = 0;
            Object.values(response.undetermined).forEach(function(element){
                let artist = document.createElement("span");
                if(count == Object.values(response.undetermined).length - 1){
                    artist.innerText=element;
                } else {
                    artist.innerText=element + ", ";
                }
                mixedGenderGroups.appendChild(artist);
                count++;
            });
        },
        error: function(xhr) {
            //Do Something to handle error
        }
    });
}