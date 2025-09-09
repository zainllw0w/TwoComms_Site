<?php
echo "PHP работает!<br>";
echo "Текущее время: " . date('Y-m-d H:i:s') . "<br>";
echo "Домен: " . $_SERVER['HTTP_HOST'] . "<br>";
echo "Путь: " . $_SERVER['REQUEST_URI'] . "<br>";
?>
