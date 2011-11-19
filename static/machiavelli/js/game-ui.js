function makeGameUI(map_url) {
	setMapHeight();
	loadMapViewer(map_url);
	$("#countries_info").dialog({resizable: false });
	$("#countries_show").click(function(){
		$("#countries_info").dialog("open");
	});
}

function setMapHeight() {
	var mapHeight = $(window).height() - $("#top_bar").height() - $("#bottom_bar").height();
	$("#map").height(mapHeight);
}

function loadMapViewer(map_url) {
	var viewer_opts = {
		src: map_url,
		ui_disabled: true,
		zoom: "fit",
		zoom_max: 100,
		zoom_min: 10,
		zoom_delta: 1.4,
		//zoom_base:
		update_on_resize: false,
		initCallback: function() {
			var object = this;
			$(window).resize(function(){ object.fit();});
		},
	};
	$("#map").iviewer(viewer_opts);
}

