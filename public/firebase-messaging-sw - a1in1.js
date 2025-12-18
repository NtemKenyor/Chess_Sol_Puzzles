importScripts('https://www.gstatic.com/firebasejs/3.7.1/firebase-app.js');
importScripts('https://www.gstatic.com/firebasejs/3.7.1/firebase-messaging.js');

// Initialize Firebase
  var config = {
    apiKey: "AIzaSyCxPPorPed2w40u3FT1LnmaKYg5xPaTk5c",
    authDomain: "a1in1-456e4.firebaseapp.com",
    databaseURL: "https://a1in1-456e4.firebaseio.com",
    storageBucket: "a1in1-456e4.appspot.com",
    messagingSenderId: "403760113486"
  };
  firebase.initializeApp(config);
  
  
// This line would: Retrieve an instance of Firebase Messaging so that it can handle background messages but I had to remove it some that I do not have two messages and just use the EventListener for push to set-up a better notification from the server items.

  //const messaging = firebase.messaging();

/*messaging.setBackgroundMessageHandler(function (payload) {

    const title = 'Firebase Web Notification';
    const options = {
        body: payload.data.body,
        icon: 'images/allin1.png',
        badge: 'images/ask.jpg'
    };

    const notificationPromise = self.registration.showNotification(title, options);
    return event.waitUntil(notificationPromise);

});*/

/*self.addEventListener('notificationclick', function(e) {
  var notification = e.notification;
  var primaryKey = notification.data.primaryKey;
  //var payload = JSON.parse(e.data.text());
  var tag  = JSON.parse(e.data.text());
  var action = e.action;
  
  if (action === 'close') {
    notification.close();
  } else {
    //clients.openWindow('https://roynek.com/alltrenders/codes/askPage.php?question='+tag);
    clients.openWindow('http://google.com?q='+tag);
    notification.close();
  }
});*/

self.addEventListener('notificationclick', function(e) {
  var notification = e.notification;
  var url = 'https://example.com';  // Specify the URL you want to open

  var action = e.action;

  if (action === 'close') {
    notification.close();
  } else {
    clients.openWindow(url);
    notification.close();
  }
});
/* 
self.addEventListener('notificationclick', function(e) {
  var notification = e.notification;
  var primaryKey = notification.data.primaryKey;
  var action = e.action;
  var url = e.tag.toString();
  
  //link to the page ..
  var link = "https://roynek.com/alltrenders/codes/askPage.php";
  if(url.includes('://')){
      link = url;
  }else{
      link = 'https://roynek.com/alltrenders/codes/askPage.php?question_title='+url;
  }
  
  //checking and taking the actions...
  if (action === 'close') {
    notification.close();
  } else {
    clients.openWindow(link);
    notification.close();
  }
});
 */


/* self.addEventListener('push', function(e) {
  var title, body, icon, image, url;

  if (e.data) {
    var payload = JSON.parse(e.data.text());
    // For those of you who love logging
    console.log(payload); 
    title  = payload.notification.title;
    body  = payload.notification.body;
    icon  = payload.notification.icon;
    image  = payload.notification.image;
    url  = payload.notification.tag.toString();
    
  } else {
    body = 'A1in1 says - Hello';
  }
  
  self.addEventListener('notificationclick', function(e) {
  var notification = e.notification;
  var primaryKey = notification.data.primaryKey;
  var action = e.action;
  
  //link to the page ..
  var link = "https://roynek.com/alltrenders/codes/askPage.php";
  
  if(url.includes('://')){
      link = url;
  }else{
      link = 'https://roynek.com/alltrenders/codes/askPage.php?question_title='+url;
  }
  if (action === 'close') {
    notification.close();
  } else {
    clients.openWindow(link);
    notification.close();
  }
});

    
  var options = {
    body: body,
    icon: icon,
    image: image,
    vibrate: [100, 50, 100],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1
    },
    actions: [
      {action: 'explore', title: 'Explore more',
        icon: 'images/checkmark.png'},
      {action: 'close', title: 'Cancel',
        icon: 'images/xmark.png'},
    ]
  };
  e.waitUntil(
    self.registration.showNotification(title, options)
  );
}); */