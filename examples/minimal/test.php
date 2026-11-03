<?php
$actual = msgpack_unpack(msgpack_pack(yaml_parse("answer: " . purifier_answer() . "\n")));
if ($actual['answer'] !== 42) throw new RuntimeException('native proof failed');
echo $actual['answer'], "\n";
