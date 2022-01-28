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
        },
        error: function(xhr) {
            //Do Something to handle error
        }
    });
}