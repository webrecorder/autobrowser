
window.addEventListener("message", function(event) {
    window.reqid = event.data.reqid;
    console.log("reqid: " + window.reqid);
});

window.addEventListener("load", function() {
  document.querySelector("#automate").addEventListener("click", function() {
    console.log("start");
    window.fetch("/api/auto/" + window.reqid);
  })
});
    


