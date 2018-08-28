window.addEventListener("message", function (event) {
  window.reqid = event.data.reqid;
  console.log("reqid: " + window.reqid);
  document.getElementById('automate').classList.replace('not-ready', 'ready');
  document.getElementById('stop').classList.replace('not-ready', 'ready');
});

window.addEventListener("load", function () {
  document.querySelector("#automate").addEventListener("click", function () {
    console.log("start");
    window.fetch("/api/autostart/" + window.reqid);
  });

  document.querySelector("#stop").addEventListener("click", function () {
    console.log("stop");
     window.fetch("/api/autostop/" + window.reqid);
  });

});
    


