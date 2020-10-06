function click_update_media_library_button() {
    console.log("click_update_media_library_button");
    $.post("/api/library/update",
    {
        'token':''
    },
    function(data,status){
        console.log("数据: \n" + data + "\n状态: " + status);
    });
}

function home_onload() {

}
