function getCookie(name){ 
  var arr,reg=new RegExp("(^| )"+name+"=([^;]*)(;|$)");
  return (arr=document.cookie.match(reg))?unescape(arr[2]):null;
}

$(document).ready(
  function(){
    $("#login_in").click(
        function(){ 
          var user = $("#InputEmail").val(); //从html中获取user值 
          var pwd1 = $("#InputPassword").val(); 
          // var pwd2 = $("#Doublepassword").val(); 
          var pdd = {"email":user, "password":pwd1};
          //这就是之前的方式，但是只能传送两个键值，没解决 
          var formData = new FormData(); //新建一个FormData对象 
          formData.append("email",user); //将需要传给后端的值通过 键/值 对形式写入FormData中
          formData.append("password",pwd1); 
          // formData.append("pwd2",pwd2); 
          formData.append("_xsrf",getCookie("_xsrf")); //得到cookie值，然后将这个值放到向后端post的数据中，如果没有添加XSRF令牌，如果没有可删除 
          $.ajax({ 
            type:"post", 
            url:"/login.html", 
            data:formData, //将formdata写入data中，发送给前端 <!--dataType : 'json', --> //服务端返回的数据类型，注意不是上面formdata的类型，是返回的，我是返回文本，所以删除 
            cache:false, //禁止浏览器将数据缓存(根据需求使用) 
            processData: false, //不处理发送的数据 
            contentType: false, //不设置内容类型 
            success:function(data){
              if(data.success){
                window.location.href='/index.html';
              }
              if(!data.success){
                alert("login fail!");
              }
              // alert(data); //成功则弹出服务端返回的数据 
            }, 
            error:function(){ 
              alert("error!"); 
            }, 
          }); 
        }); 
      }
);