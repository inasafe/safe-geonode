var layers = undefined;
var functions = undefined;
var questions = undefined;

var hazard_layer = undefined;
var exposure_layer = undefined;

var map = undefined;
var result = undefined;

var markers = undefined;

$("#reset").click(function() {
    remove_exposure();
    remove_hazard();
    safe_init();
    map.fitWorld();
    $("#result").css("display", "none");
    $("#calculation").css("display", "none");
    $("#reset").css("display", "none"); 
    $(".barlittle").css("display", "none");
    $("#answermark").css("display", "none");
    $("#answer").animate({height:"0px"},420);
    $('#functionlist').html('');
    $('#exposurelist').html('');
    $('#hazardlist').html('');
    $(".leaflet-bottom").css("bottom", "70px");
});


function remove_exposure(){
    if (exposure_layer !== undefined){
        if (map.hasLayer(exposure_layer)){
            map.removeLayer(exposure_layer);
        }
    }    
}

function remove_hazard(){
    if (hazard_layer !== undefined){
        if (map.hasLayer(hazard_layer)){
            map.removeLayer(hazard_layer);
        }
    }    
}

function add_hazard_layer(layer_name){
    layer = layers[layer_name];
    hazard_layer = L.tileLayer(layer.tile_url);
    hazard_layer.setOpacity(0.8);
    hazard_layer.addTo(map);

    // Center the map on the extent of the hazard layer
    var bbox = layer.bounding_box;
    var zoom = map.getZoom();
    var bounds = [
        [bbox[1], bbox[0]],
        [bbox[3], bbox[2]]
    ];
    var center = [(bbox[1]+bbox[3])/2, (bbox[0]+ bbox[2])/2];
    map.setView(center, zoom);
    map.fitBounds(bounds);
}

function add_exposure_layer(layer_name){
    layer = layers[layer_name];
    exposure_layer = L.tileLayer(layer.tile_url);
    exposure_layer.setOpacity(0.5);
    exposure_layer.addTo(map);
}

function calculation_error(data){ 
    $(".barlittle").css("display", "none");
    $("#result").css("display", "inline");
    $("#reset").css("display", "inline");
    output = "<div class=\"alert alert-error\">" +
                "<a class=\"close\" data-dismiss=\"alert\">×</a>" +
                "<h1>Calculation Failed</h1>" +
                "<p>" + data.errors + "</p></div>";
    $("#result").html(output);
}

function calculate(hazard_name, exposure_name, function_name) {
        var bounds = map.getBounds();
        var minll= bounds.getSouthWest();
        var maxll= bounds.getNorthEast();
        var bbox = ''+minll.lng+','+minll.lat+','+maxll.lng+','+maxll.lat;

        the_hazard = layers[hazard_name]
        the_exposure = layers[exposure_name]

        $.ajax({
            type: 'POST',
            url: '/safe/api/v1/calculate/',
            data: {
                hazard_server: the_hazard.server_url,
                hazard: hazard_name,
                exposure_server: the_exposure.server_url,
                exposure: exposure_name,
                bbox: bbox,
                keywords: 'safe',
                impact_function: function_name
            },
            success: received,
            error: calculation_error
        });
};

function get_options(items){
    var options = "<option value=\"\">-> Choose one ...</option>";
    for(var key in items){
        if (items.hasOwnProperty(key)){
            option = "<option value='" + key +"'>" +
                 items[key] + "</option>";
            options = options + "\n" + option;
        }
    }
    return options;
};

function received(data) {
    $(".barlittle").css("display", "none");
    $("#reset").css("display", "inline");
    $("#calculation").css("display", "inline");

    if (data.errors !== null){
        calculation_error(data);
        return;
    }

    result = data;
    $("#result").css("display", "inline");
    $("#result").addClass('well');

    markers = new L.MarkerClusterGroup();

    var inundated = 0;
    for (var i=0; i < result.raw.data.length; i++){

        var it = result.raw.data[i];
        var point = result.raw.geometry[i];
        if (it.INUNDATED==true){
            title = 'OSM Id: ' + it.osm_id;
            var marker = new L.Marker(new L.LatLng(point[1], point[0]),  { title: title });
            marker.bindPopup(title);
            markers.addLayer(marker);
            inundated ++;
        }
    }

    map.addLayer(markers);

    var total = result.raw.data.length;

    // Set caption for title
    $("#calculation > .page-header > h1").html(inundated + " buildings" + 
                                    " <small>would have to be closed from a total of " +
                                    total + "</small>");

    $("#result > #summary > p").html(result.raw.summary);

    table_rows = $("#result p table tbody tr");

    actions = []

    for (var i=5; i < 10; i++){
        action = $("#result p table tbody tr:nth-child(" + i +") td").html();
        actions.push(action);
    }

    note = $("#result p table tbody tr:nth-child(11) td").html()

    summary = "<ul>";
    for (var i in actions){
        summary = summary + "<li>" + actions[i] + "</li>";
    }
    summary = summary + "</ul>";

    $("#summary").html(summary);

    $('#duration').html(result.run_duration + ' seconds')

    run_date = result.run_date.split('.')[0].split('("')[1];
    $('#date').html(run_date)
};

function_change = function(r){
    disable_all();
    $("#answer").animate({height:"300px"},400);
    $(".barlittle").css("display", "inline");
    $("#answermark").css("display", "inline");

    $(".leaflet-bottom").css("bottom", "370px");

    hazard_name =  $('#hazardlist option:selected').val();
    exposure_name =  $('#exposurelist option:selected').val();
    function_name =  $('#functionlist option:selected').val();
    calculate(hazard_name, exposure_name, function_name);
};

questions_received = function(r){
    questions = r.questions;
    functions = r.functions;
    layers = r.layers;

    var valid_hazards = {};
    for (i in questions){
        question = questions[i];
        valid_hazards[question.hazard] = layers[question.hazard].title;
    }
    hazard_populate(valid_hazards);
}

function_populate = function(valid_functions){
    function_options = get_options(valid_functions);

    $('#functionlist').html('');
    $('#functionlist').html(function_options);
    $('#functionlist').removeAttr('disabled');
    $('#functionlabel').css('opacity', 1);
    $('#functionlist').change(function_change);
};


exposure_change = function() {
    hazard_name =  $('#hazardlist option:selected').val();
    exposure_name =  $('#exposurelist option:selected').val();

    // Add layer to the map
    add_exposure_layer(exposure_name);

    var valid_functions = {};
    for (i in questions){
        question = questions[i];
        if ((question.hazard == hazard_name) && (question.exposure == exposure_name)){
            valid_functions[question.function] = functions[question.function].title;
        }
    }
    function_populate(valid_functions);
};

exposure_populate = function(valid_exposures) {
    exposure_options = get_options(valid_exposures);
    $('#exposurelist').html('');
    $('#exposurelist').html(exposure_options);
    $('#exposurelist').removeAttr('disabled');
    $('#exposurelabel').css('opacity', 1); 

    $('#exposurelist').change(exposure_change);
};

hazard_change = function() {
    hazard_name =  $('#hazardlist option:selected').val();
    add_hazard_layer(hazard_name);

    // Filter the list of exposures that can be used with this dataset.
    var valid_exposures = {};
    for (i in questions){
        question = questions[i];
        if (question.hazard == hazard_name){
            valid_exposures[question.exposure] = layers[question.exposure].title;
        }
    }
    exposure_populate(valid_exposures);
};

hazard_populate = function(valid_hazards){
    hazard_options = get_options(valid_hazards, 'name', 'title');
    $("#hazardlist").html(hazard_options);
    $('#hazardlist').attr('disabled', false);
    // wire this after initializing, to avoid enabling the exposure one before time
    $('#hazardlist').change(hazard_change);
};

function disable_all(){
    $('#hazardlist').attr('disabled', true);
    $('#exposurelist').attr('disabled', true);
    $('#functionlist').attr('disabled', true);
}

function safe_init(){
    // Save reference to map object.
    map = window.maps.pop();
    window.maps.push(map);

    disable_all();
    $('#exposurelabel').css('opacity', 0.1);
    $('#functionlabel').css('opacity', 0.1);

    $.ajax({
      url: "/safe/api/v1/questions/",  
      success: questions_received,
      error: function(r){  
        alert('Error: ' + r);  
      }  
    });
}

function safemapInit(map, bounds){
    // Add attribution (to replace, Powered by Leaflet)
    map.attributionControl.setPrefix('Powered by MapBox Streets and OSM data');

    // Initialize safe forms
    safe_init();
}